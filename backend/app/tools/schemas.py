from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import AgentRole


ToolFailureCode: TypeAlias = Literal[
    "unknown_tool",
    "handler_unavailable",
    "access_denied",
    "approval_required",
    "approval_invalid",
    "input_validation_error",
    "idempotency_key_required",
    "idempotency_conflict",
    "timeout",
    "transient_error",
    "output_validation_error",
    "handler_error",
]


class RetryPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_attempts: int = Field(ge=1, le=5)
    initial_backoff_seconds: float = Field(ge=0, le=5)
    backoff_multiplier: float = Field(ge=1, le=4)
    max_backoff_seconds: float = Field(ge=0, le=30)
    retry_on: frozenset[Literal["transient_error", "timeout"]]


class ToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    tool_name: str
    tenant_id: str
    target_tenant_id: str
    workflow_id: str
    actor_id: str
    agent_role: AgentRole
    trace_id: str
    actor_permissions: set[str]
    arguments: dict[str, Any]
    approval_id: str | None = None
    idempotency_key: str | None = None


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: Literal[True]
    request_id: str
    tool_name: str
    tool_version: str
    tenant_id: str
    workflow_id: str
    trace_id: str
    output: dict[str, Any]
    attempts: int
    duration_ms: int
    replayed: bool


class ToolFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: Literal[False]
    request_id: str
    tool_name: str
    tool_version: str | None
    tenant_id: str
    workflow_id: str
    trace_id: str
    code: ToolFailureCode
    message: str
    details: list[str]
    retryable: bool
    attempts: int
    duration_ms: int


ToolExecutionResult: TypeAlias = ToolResult | ToolFailure


class ToolExecutionContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    tenant_id: str
    target_tenant_id: str
    workflow_id: str
    actor_id: str
    agent_role: AgentRole
    trace_id: str
    approval_id: str | None = None
    idempotency_key: str | None = None


ToolHandler: TypeAlias = Callable[
    [BaseModel, ToolExecutionContext],
    Awaitable[BaseModel | Mapping[str, Any]],
]
