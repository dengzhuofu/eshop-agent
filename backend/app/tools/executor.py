import asyncio
import hashlib
import json
import time
from collections.abc import Mapping
from typing import Protocol

from pydantic import BaseModel, ValidationError

from app.agents.observability.schema import TraceEventType, create_trace_event
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


class TransientToolError(RuntimeError):
    pass


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._results: dict[tuple[str, str, str, str], tuple[str, ToolResult]] = {}
        self._locks: dict[tuple[str, str, str, str], asyncio.Lock] = {}

    def lock_for(self, identity: tuple[str, str, str, str]) -> asyncio.Lock:
        lock = self._locks.get(identity)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[identity] = lock
        return lock

    def get(
        self,
        identity: tuple[str, str, str, str],
    ) -> tuple[str, ToolResult] | None:
        stored = self._results.get(identity)
        if stored is None:
            return None
        input_hash, result = stored
        return input_hash, result.model_copy(deep=True)

    def save(
        self,
        identity: tuple[str, str, str, str],
        input_hash: str,
        result: ToolResult,
    ) -> None:
        self._results[identity] = (input_hash, result.model_copy(deep=True))


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
        input_hash = _canonical_hash(input_data.model_dump(mode="json"))
        idempotency_key_hash = (
            _hash_text(request.idempotency_key) if request.idempotency_key is not None else None
        )

        if tool.idempotent and request.idempotency_key is None:
            return self._failure(
                request,
                started_at,
                code="idempotency_key_required",
                message="Idempotency key is required.",
                tool_version=tool.version,
                attempts=0,
            )

        if tool.idempotent:
            identity = (
                request.tenant_id,
                tool.name,
                tool.version,
                request.idempotency_key,
            )
            # 同一幂等身份串行检查与执行，防止并发请求同时越过缓存检查。
            async with self._idempotency_store.lock_for(identity):
                cached = self._idempotency_store.get(identity)
                if cached is not None:
                    cached_hash, cached_result = cached
                    if cached_hash != input_hash:
                        return self._failure(
                            request,
                            started_at,
                            code="idempotency_conflict",
                            message="Idempotency key conflicts with different input.",
                            tool_version=tool.version,
                            attempts=0,
                        )
                    return cached_result.model_copy(
                        update={
                            "request_id": request.request_id,
                            "tenant_id": request.tenant_id,
                            "workflow_id": request.workflow_id,
                            "trace_id": request.trace_id,
                            "attempts": 0,
                            "duration_ms": self._duration_ms(started_at),
                            "replayed": True,
                        },
                        deep=True,
                    )

                result = await self._execute_attempts(
                    request=request,
                    tool=tool,
                    handler=handler,
                    input_data=input_data,
                    context=context,
                    started_at=started_at,
                    input_hash=input_hash,
                    idempotency_key_hash=idempotency_key_hash,
                )
                # 失败不进入缓存，后续同键请求仍可重新尝试。
                if isinstance(result, ToolResult):
                    self._idempotency_store.save(identity, input_hash, result)
                return result

        return await self._execute_attempts(
            request=request,
            tool=tool,
            handler=handler,
            input_data=input_data,
            context=context,
            started_at=started_at,
            input_hash=input_hash,
            idempotency_key_hash=idempotency_key_hash,
        )

    async def _execute_attempts(
        self,
        *,
        request: ToolRequest,
        tool: ToolDefinition,
        handler,
        input_data: BaseModel,
        context: ToolExecutionContext,
        started_at: float,
        input_hash: str,
        idempotency_key_hash: str | None,
    ) -> ToolExecutionResult:
        for attempt in range(1, tool.retry_policy.max_attempts + 1):
            attempt_started_at = self._clock()
            failure_code: ToolFailureCode | None = None
            failure_details: list[str] = []
            output_data: BaseModel | None = None

            try:
                raw_output = await asyncio.wait_for(
                    handler(input_data, context),
                    timeout=tool.timeout_seconds,
                )
            except asyncio.TimeoutError:
                failure_code = "timeout"
            except TransientToolError:
                failure_code = "transient_error"
            except Exception:
                failure_code = "handler_error"
            else:
                if isinstance(raw_output, BaseModel):
                    output_payload = raw_output.model_dump()
                elif isinstance(raw_output, Mapping):
                    output_payload = dict(raw_output)
                else:
                    output_payload = raw_output
                try:
                    output_data = tool.output_model.model_validate(output_payload)
                except ValidationError as exc:
                    failure_code = "output_validation_error"
                    failure_details = _validation_details(exc)

            retryable = failure_code in tool.retry_policy.retry_on
            self._record_attempt(
                request=request,
                tool=tool,
                input_hash=input_hash,
                idempotency_key_hash=idempotency_key_hash,
                attempt=attempt,
                attempt_started_at=attempt_started_at,
                status="succeeded" if failure_code is None else "failed",
                failure_code=failure_code,
                retryable=retryable,
            )

            if failure_code is None and output_data is not None:
                return ToolResult(
                    ok=True,
                    request_id=request.request_id,
                    tool_name=request.tool_name,
                    tool_version=tool.version,
                    tenant_id=request.tenant_id,
                    workflow_id=request.workflow_id,
                    trace_id=request.trace_id,
                    output=output_data.model_dump(mode="json"),
                    attempts=attempt,
                    duration_ms=self._duration_ms(started_at),
                    replayed=False,
                )

            if retryable and attempt < tool.retry_policy.max_attempts:
                delay = min(
                    tool.retry_policy.initial_backoff_seconds
                    * (tool.retry_policy.backoff_multiplier ** (attempt - 1)),
                    tool.retry_policy.max_backoff_seconds,
                )
                await self._sleeper(delay)
                continue

            return self._failure(
                request,
                started_at,
                code=failure_code or "handler_error",
                message=_failure_message(failure_code or "handler_error"),
                tool_version=tool.version,
                details=failure_details,
                retryable=retryable,
                attempts=attempt,
            )

        raise RuntimeError("tool execution attempt loop did not return")

    def _record_attempt(
        self,
        *,
        request: ToolRequest,
        tool: ToolDefinition,
        input_hash: str,
        idempotency_key_hash: str | None,
        attempt: int,
        attempt_started_at: float,
        status: str,
        failure_code: ToolFailureCode | None,
        retryable: bool,
    ) -> None:
        self._trace_repository.record(
            create_trace_event(
                workflow_id=request.workflow_id,
                tenant_id=request.tenant_id,
                agent_role=request.agent_role,
                event_type=TraceEventType.TOOL_CALL,
                name=request.tool_name,
                metadata={
                    "request_id": request.request_id,
                    "trace_id": request.trace_id,
                    "tool_version": tool.version,
                    "input_hash": input_hash,
                    "attempt": attempt,
                    "max_attempts": tool.retry_policy.max_attempts,
                    "status": status,
                    "duration_ms": self._duration_ms(attempt_started_at),
                    "failure_code": failure_code,
                    "retryable": retryable,
                    "idempotency_key_hash": idempotency_key_hash,
                },
            )
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


def _canonical_hash(payload: dict) -> str:
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return _hash_text(canonical)


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _failure_message(code: ToolFailureCode) -> str:
    messages: dict[ToolFailureCode, str] = {
        "unknown_tool": "Tool is not registered.",
        "handler_unavailable": "Tool handler is unavailable.",
        "access_denied": "Tool access was denied.",
        "approval_required": "Approved proof is required.",
        "approval_invalid": "Approval proof is invalid.",
        "input_validation_error": "Tool input failed validation.",
        "idempotency_key_required": "Idempotency key is required.",
        "idempotency_conflict": "Idempotency key conflicts with different input.",
        "timeout": "Tool handler timed out.",
        "transient_error": "Tool handler reported a transient failure.",
        "output_validation_error": "Tool output failed validation.",
        "handler_error": "Tool handler failed.",
    }
    return messages[code]
