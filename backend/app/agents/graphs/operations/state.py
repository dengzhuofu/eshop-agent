from typing import Literal, TypedDict

from app.domain.enums import AgentRole
from app.domain.operations import (
    OperationsReadError,
    OperationsReadModel,
    OperationsReadQuery,
    OpsActionProposal,
    OpsAnomaly,
    OpsEvidence,
    OpsFailure,
    OpsPerformanceSummary,
    OpsTraceSummary,
)


OpsWorkflowStatus = Literal["queued", "running", "completed", "failed", "insufficient_data"]
OpsRouteDecision = Literal["analyze", "complete"]


class OpsAgentState(TypedDict):
    workflow_id: str
    tenant_id: str
    current_agent: AgentRole
    current_step: str
    status: OpsWorkflowStatus
    route_decision: OpsRouteDecision
    query: OperationsReadQuery
    read_model: OperationsReadModel | None
    summaries: list[OpsPerformanceSummary]
    anomalies: list[OpsAnomaly]
    evidence: list[OpsEvidence]
    proposals: list[OpsActionProposal]
    failure: OpsFailure | None
    completed_steps: list[str]
    trace_summaries: list[OpsTraceSummary]


def create_initial_operations_state(
    *,
    workflow_id: str,
    tenant_id: str,
    query: OperationsReadQuery,
) -> OpsAgentState:
    if query.tenant_id != tenant_id:
        raise OperationsReadError(
            code="tenant_mismatch",
            tenant_id=tenant_id,
            message="Operations query tenant does not match workflow tenant.",
        )
    return {
        "workflow_id": workflow_id,
        "tenant_id": tenant_id,
        "current_agent": AgentRole.OPS,
        "current_step": "queued",
        "status": "queued",
        "route_decision": "analyze",
        "query": query,
        "read_model": None,
        "summaries": [],
        "anomalies": [],
        "evidence": [],
        "proposals": [],
        "failure": None,
        "completed_steps": [],
        "trace_summaries": [],
    }
