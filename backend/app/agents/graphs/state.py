from typing import Any, TypedDict

from app.domain.enums import AgentRole, RiskLevel


class CommerceAgentState(TypedDict):
    workflow_id: str
    tenant_id: str
    current_agent: AgentRole
    current_step: str
    messages: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    approval_required: bool
    approval_request_id: str | None
    risk_level: RiskLevel
    evidence: list[dict[str, Any]]
    errors: list[str]


def create_initial_state(
    workflow_id: str,
    tenant_id: str,
    current_agent: AgentRole,
) -> CommerceAgentState:
    return {
        "workflow_id": workflow_id,
        "tenant_id": tenant_id,
        "current_agent": current_agent,
        "current_step": "queued",
        "messages": [],
        "tool_calls": [],
        "approval_required": False,
        "approval_request_id": None,
        "risk_level": RiskLevel.LOW,
        "evidence": [],
        "errors": [],
    }

