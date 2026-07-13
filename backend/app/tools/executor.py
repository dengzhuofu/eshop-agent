import asyncio
import time
from collections.abc import Mapping
from typing import Protocol

from pydantic import BaseModel, ValidationError

from app.domain.enums import ApprovalStatus
from app.repositories.approvals import ApprovalRepository
from app.repositories.events import TraceEventRepository
from app.security.boundary import AgentBoundaryPolicy, ToolAccessContext
from app.tools.catalog import ToolHandlerCatalog
from app.tools.registry import ToolDefinition, ToolRegistry
from app.tools.schemas import (
    ToolExecutionContext,
    ToolExecutionResult,
    ToolFailure,
    ToolFailureCode,
    ToolRequest,
    ToolResult,
)


class ApprovalProofVerifier(Protocol):
    def verify(self, request: ToolRequest, tool: ToolDefinition) -> tuple[bool, list[str]]: ...


class RepositoryApprovalProofVerifier:
    def __init__(self, repository: ApprovalRepository) -> None:
        self._repository = repository

    def verify(self, request: ToolRequest, tool: ToolDefinition) -> tuple[bool, list[str]]:
        approval = self._repository.get(request.approval_id)
        if approval is None:
            return False, ["approval proof not found"]

        # 审批必须绑定本次执行身份，不能只凭一个已批准 ID 放行其他调用。
        reasons: list[str] = []
        if approval.status != ApprovalStatus.APPROVED:
            reasons.append("approval status is not approved")
        if approval.tenant_id != request.tenant_id:
            reasons.append("approval tenant mismatch")
        if approval.workflow_id != request.workflow_id:
            reasons.append("approval workflow mismatch")
        if approval.metadata.get("tool") != tool.name:
            reasons.append("approval tool mismatch")
        approved_key = approval.metadata.get("idempotency_key")
        if approved_key is not None and approved_key != request.idempotency_key:
            reasons.append("approval idempotency key mismatch")
        return not reasons, reasons


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._results: dict[tuple[str, str, str, str], tuple[str, ToolResult]] = {}
        self._locks: dict[tuple[str, str, str, str], asyncio.Lock] = {}


class ToolExecutor:
    def __init__(
        self,
        *,
        registry: ToolRegistry,
        handlers: ToolHandlerCatalog,
        boundary_policy: AgentBoundaryPolicy,
        approval_verifier: ApprovalProofVerifier,
        idempotency_store: InMemoryIdempotencyStore,
        trace_repository: TraceEventRepository,
        sleeper=asyncio.sleep,
        clock=time.perf_counter,
    ) -> None:
        self._registry = registry
        self._handlers = handlers
        self._boundary_policy = boundary_policy
        self._approval_verifier = approval_verifier
        self._idempotency_store = idempotency_store
        self._trace_repository = trace_repository
        self._sleeper = sleeper
        self._clock = clock

    async def execute(self, request: ToolRequest) -> ToolExecutionResult:
        started_at = self._clock()
        try:
            tool = self._registry.get(request.tool_name)
        except KeyError:
            return self._failure(
                request,
                started_at,
                code="unknown_tool",
                message="Tool is not registered.",
                tool_version=None,
                attempts=0,
            )

        try:
            handler = self._handlers.get(request.tool_name)
        except KeyError:
            return self._failure(
                request,
                started_at,
                code="handler_unavailable",
                message="Tool handler is unavailable.",
                tool_version=tool.version,
                attempts=0,
            )

        access_context = ToolAccessContext(
            agent_role=request.agent_role,
            tool_name=request.tool_name,
            actor_tenant_id=request.tenant_id,
            target_tenant_id=request.target_tenant_id,
            actor_permissions=request.actor_permissions,
            approved=False,
            payload=request.arguments,
        )
        initial_decision = self._boundary_policy.evaluate_tool_access(access_context)
        non_approval_reasons = [
            reason for reason in initial_decision.reasons if reason != "approval required"
        ]
        if non_approval_reasons:
            return self._failure(
                request,
                started_at,
                code="access_denied",
                message="Tool access was denied.",
                tool_version=tool.version,
                details=non_approval_reasons,
                attempts=0,
            )

        if tool.requires_approval:
            if request.approval_id is None:
                return self._failure(
                    request,
                    started_at,
                    code="approval_required",
                    message="Approved proof is required.",
                    tool_version=tool.version,
                    details=["approval proof missing"],
                    attempts=0,
                )

            proof_valid, proof_reasons = self._approval_verifier.verify(request, tool)
            if not proof_valid:
                return self._failure(
                    request,
                    started_at,
                    code="approval_invalid",
                    message="Approval proof is invalid.",
                    tool_version=tool.version,
                    details=proof_reasons,
                    attempts=0,
                )

            # 证明只解除 approval required；其余边界必须再次独立成立。
            approved_decision = self._boundary_policy.evaluate_tool_access(
                access_context.model_copy(update={"approved": True})
            )
            if not approved_decision.allowed:
                return self._failure(
                    request,
                    started_at,
                    code="access_denied",
                    message="Tool access was denied.",
                    tool_version=tool.version,
                    details=approved_decision.reasons,
                    attempts=0,
                )

        if tool.input_model is None or tool.output_model is None:
            return self._failure(
                request,
                started_at,
                code="handler_unavailable",
                message="Tool schema is unavailable.",
                tool_version=tool.version,
                attempts=0,
            )

        try:
            input_data = tool.input_model.model_validate(request.arguments)
        except ValidationError as exc:
            return self._failure(
                request,
                started_at,
                code="input_validation_error",
                message="Tool input failed validation.",
                tool_version=tool.version,
                details=_validation_details(exc),
                attempts=0,
            )

        context = ToolExecutionContext(
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            target_tenant_id=request.target_tenant_id,
            workflow_id=request.workflow_id,
            actor_id=request.actor_id,
            agent_role=request.agent_role,
            trace_id=request.trace_id,
            approval_id=request.approval_id,
            idempotency_key=request.idempotency_key,
        )
        try:
            raw_output = await handler(input_data, context)
        except Exception:
            return self._failure(
                request,
                started_at,
                code="handler_error",
                message="Tool handler failed.",
                tool_version=tool.version,
                attempts=1,
            )

        if isinstance(raw_output, BaseModel):
            output_payload = raw_output.model_dump()
        elif isinstance(raw_output, Mapping):
            output_payload = dict(raw_output)
        else:
            output_payload = raw_output

        try:
            output_data = tool.output_model.model_validate(output_payload)
        except ValidationError as exc:
            return self._failure(
                request,
                started_at,
                code="output_validation_error",
                message="Tool output failed validation.",
                tool_version=tool.version,
                details=_validation_details(exc),
                attempts=1,
            )

        return ToolResult(
            ok=True,
            request_id=request.request_id,
            tool_name=request.tool_name,
            tool_version=tool.version,
            tenant_id=request.tenant_id,
            workflow_id=request.workflow_id,
            trace_id=request.trace_id,
            output=output_data.model_dump(mode="json"),
            attempts=1,
            duration_ms=self._duration_ms(started_at),
            replayed=False,
        )

    def _failure(
        self,
        request: ToolRequest,
        started_at: float,
        *,
        code: ToolFailureCode,
        message: str,
        tool_version: str | None,
        details: list[str] | None = None,
        retryable: bool = False,
        attempts: int,
    ) -> ToolFailure:
        return ToolFailure(
            ok=False,
            request_id=request.request_id,
            tool_name=request.tool_name,
            tool_version=tool_version,
            tenant_id=request.tenant_id,
            workflow_id=request.workflow_id,
            trace_id=request.trace_id,
            code=code,
            message=message,
            details=details or [],
            retryable=retryable,
            attempts=attempts,
            duration_ms=self._duration_ms(started_at),
        )

    def _duration_ms(self, started_at: float) -> int:
        return max(0, round((self._clock() - started_at) * 1000))


def _validation_details(exc: ValidationError) -> list[str]:
    details: list[str] = []
    for error in exc.errors(include_url=False, include_context=False, include_input=False):
        location = ".".join(str(part) for part in error["loc"]) or "payload"
        details.append(f"{location}: {error['type']}")
    return details
