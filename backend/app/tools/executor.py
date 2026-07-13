import asyncio
import time
from collections.abc import Mapping
from typing import Protocol

from pydantic import BaseModel, ValidationError

from app.repositories.events import TraceEventRepository
from app.security.boundary import AgentBoundaryPolicy
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
