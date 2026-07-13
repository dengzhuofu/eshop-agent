from __future__ import annotations

from hashlib import sha256

from app.adapters.operations import OperationsReadPort
from app.agents.graphs.operations.state import OpsAgentState
from app.domain.enums import AgentRole
from app.domain.operations import (
    OperationsReadError,
    OperationsReadModel,
    OpsFailure,
    OpsTraceSummary,
    TraceDecision,
)
from app.services.operations import (
    build_operations_read_model,
    detect_ops_anomalies,
    propose_ops_actions,
    summarize_operations,
)


def _freshness(read_model: OperationsReadModel | None) -> str:
    if read_model is None:
        return "not_loaded"
    if not read_model.records:
        return "empty"
    if not read_model.fresh_records:
        return "all_stale"
    if read_model.stale_records:
        return "partial"
    return "fresh"


def _trace_summary(
    state: OpsAgentState,
    *,
    step: str,
    decision: TraceDecision,
    read_model: OperationsReadModel | None = None,
    failure: OpsFailure | None = None,
    anomalies=None,
    evidence=None,
    proposals=None,
) -> OpsTraceSummary:
    model = read_model if read_model is not None else state.get("read_model")
    selected_anomalies = anomalies if anomalies is not None else state.get("anomalies", [])
    selected_evidence = evidence if evidence is not None else state.get("evidence", [])
    selected_proposals = proposals if proposals is not None else state.get("proposals", [])
    selected_failure = failure if failure is not None else state.get("failure")
    source_event_ids = sorted(
        {record.event_id for record in model.records} if model is not None else set()
    )
    listing_version_ids = sorted(
        {record.listing_version_id for record in model.records}
        if model is not None
        else set()
    )
    anomaly_ids = [item.anomaly_id for item in selected_anomalies]
    evidence_ids = [item.evidence_id for item in selected_evidence]
    proposal_ids = [item.proposal_id for item in selected_proposals]
    error_codes = [selected_failure.code] if selected_failure is not None else []
    material = "|".join(
        [
            state["workflow_id"],
            state["tenant_id"],
            step,
            decision,
            *source_event_ids,
            *listing_version_ids,
            *anomaly_ids,
            *evidence_ids,
            *proposal_ids,
            *error_codes,
        ]
    )
    trace_id = f"ops_trace_{sha256(material.encode('utf-8')).hexdigest()[:20]}"
    return OpsTraceSummary(
        trace_id=trace_id,
        workflow_id=state["workflow_id"],
        tenant_id=state["tenant_id"],
        agent_role=AgentRole.OPS,
        step=step,
        source_event_ids=source_event_ids,
        listing_version_ids=listing_version_ids,
        anomaly_ids=anomaly_ids,
        evidence_ids=evidence_ids,
        proposal_ids=proposal_ids,
        record_count=len(model.records) if model is not None else 0,
        fresh_record_count=len(model.fresh_records) if model is not None else 0,
        stale_record_count=len(model.stale_records) if model is not None else 0,
        freshness=_freshness(model),
        decision=decision,
        error_codes=error_codes,
    )


def load_operations_node(
    state: OpsAgentState,
    *,
    port: OperationsReadPort,
) -> dict:
    try:
        read_model = build_operations_read_model(port, state["query"])
    except OperationsReadError as exc:
        # adapter/service 的失败在图边界重新绑定 workflow tenant，且不回显底层异常 payload。
        failure = OpsFailure(
            tenant_id=state["tenant_id"],
            code=exc.code,
            message=exc.failure.message,
            source_event_ids=exc.failure.source_event_ids,
            listing_version_ids=exc.failure.listing_version_ids,
        )
        trace = _trace_summary(
            state,
            step="load_operations",
            decision="failed",
            failure=failure,
        )
        return {
            "current_step": "load_operations",
            "status": "failed",
            "route_decision": "complete",
            "read_model": None,
            "summaries": [],
            "failure": failure,
            "completed_steps": [*state["completed_steps"], "load_operations"],
            "trace_summaries": [*state["trace_summaries"], trace],
        }

    summaries = summarize_operations(read_model)
    insufficient = not read_model.fresh_records
    decision = "insufficient_data" if insufficient else "loaded"
    trace = _trace_summary(
        state,
        step="load_operations",
        decision=decision,
        read_model=read_model,
    )
    return {
        "current_step": "load_operations",
        "status": "insufficient_data" if insufficient else "running",
        "route_decision": "complete" if insufficient else "analyze",
        "read_model": read_model,
        "summaries": summaries,
        "failure": None,
        "completed_steps": [*state["completed_steps"], "load_operations"],
        "trace_summaries": [*state["trace_summaries"], trace],
    }


def route_node(state: OpsAgentState) -> dict:
    decision = (
        "analyze" if state["route_decision"] == "analyze" else state["status"]
    )
    trace = _trace_summary(state, step="route", decision=decision)
    return {
        "current_step": "route",
        "completed_steps": [*state["completed_steps"], "route"],
        "trace_summaries": [*state["trace_summaries"], trace],
    }


def detect_anomalies_node(state: OpsAgentState) -> dict:
    read_model = state["read_model"]
    if read_model is None:
        failure = OpsFailure(
            tenant_id=state["tenant_id"],
            code="source_read_failed",
            message="Operations read model is unavailable.",
        )
        trace = _trace_summary(
            state,
            step="detect_anomalies",
            decision="failed",
            failure=failure,
        )
        return {
            "current_step": "detect_anomalies",
            "status": "failed",
            "route_decision": "complete",
            "failure": failure,
            "completed_steps": [*state["completed_steps"], "detect_anomalies"],
            "trace_summaries": [*state["trace_summaries"], trace],
        }
    anomalies, evidence = detect_ops_anomalies(read_model)
    trace = _trace_summary(
        state,
        step="detect_anomalies",
        decision="detected",
        anomalies=anomalies,
        evidence=evidence,
    )
    return {
        "current_step": "detect_anomalies",
        "anomalies": anomalies,
        "evidence": evidence,
        "completed_steps": [*state["completed_steps"], "detect_anomalies"],
        "trace_summaries": [*state["trace_summaries"], trace],
    }


def propose_actions_node(state: OpsAgentState) -> dict:
    proposals = propose_ops_actions(
        workflow_id=state["workflow_id"],
        tenant_id=state["tenant_id"],
        anomalies=state["anomalies"],
    )
    trace = _trace_summary(
        state,
        step="propose_actions",
        decision="proposed",
        proposals=proposals,
    )
    return {
        "current_step": "propose_actions",
        "proposals": proposals,
        "completed_steps": [*state["completed_steps"], "propose_actions"],
        "trace_summaries": [*state["trace_summaries"], trace],
    }


def complete_node(state: OpsAgentState) -> dict:
    final_status = (
        state["status"]
        if state["status"] in {"failed", "insufficient_data"}
        else "completed"
    )
    decision = final_status
    trace = _trace_summary(state, step="complete", decision=decision)
    return {
        "current_step": "complete",
        "status": final_status,
        "route_decision": "complete",
        "completed_steps": [*state["completed_steps"], "complete"],
        "trace_summaries": [*state["trace_summaries"], trace],
    }
