from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import AgentRole


class TraceEventType(StrEnum):
    NODE_START = "node_start"
    NODE_END = "node_end"
    CHECKPOINT = "checkpoint"
    TOOL_DECISION = "tool_decision"
    TOOL_CALL = "tool_call"
    APPROVAL = "approval"
    EVALUATION = "evaluation"
    ERROR = "error"


class TraceEvent(BaseModel):
    workflow_id: str
    tenant_id: str
    agent_role: AgentRole
    event_type: TraceEventType
    name: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


def create_trace_event(
    workflow_id: str,
    tenant_id: str,
    agent_role: AgentRole,
    event_type: TraceEventType,
    name: str,
    metadata: dict[str, Any] | None = None,
) -> TraceEvent:
    return TraceEvent(
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        agent_role=agent_role,
        event_type=event_type,
        name=name,
        metadata=metadata or {},
        created_at=datetime.now(timezone.utc),
    )
