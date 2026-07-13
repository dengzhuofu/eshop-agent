from langgraph.graph import END, START, StateGraph

from app.agents.observability.schema import TraceEventType, create_trace_event
from app.agents.graphs.nodes.listings import (
    await_approval_node,
    listing_validation_node,
    localization_node,
    publish_listing_node,
)
from app.agents.graphs.nodes.product_launch import (
    complete_node,
    product_research_node,
    profit_analysis_node,
    risk_review_node,
    supplier_evaluation_node,
)
from app.agents.graphs.routes.product_launch import route_after_risk_review
from app.agents.graphs.state import CommerceAgentState, create_initial_state
from app.domain.enums import AgentRole, Marketplace, WorkflowState
from app.repositories.approvals import get_approval_repository
from app.repositories.events import get_trace_event_repository
from app.repositories.snapshots import get_workflow_snapshot_repository
from app.services.listing_versions import listing_version_summary

STEP_AGENT_ROLES = {
    "product_research": AgentRole.PRODUCT_RESEARCH,
    "profit_analysis": AgentRole.PROFIT_ANALYST,
    "supplier_evaluation": AgentRole.SUPPLIER,
    "localization": AgentRole.LOCALIZATION,
    "listing_validation": AgentRole.LISTING,
    "risk_review": AgentRole.RISK_REVIEW,
    "await_approval": AgentRole.SUPERVISOR,
    "publish_listing": AgentRole.SUPERVISOR,
    "complete": AgentRole.SUPERVISOR,
}


def build_product_launch_graph():
    graph = StateGraph(CommerceAgentState)
    graph.add_node("product_research", product_research_node)
    graph.add_node("profit_analysis", profit_analysis_node)
    graph.add_node("supplier_evaluation", supplier_evaluation_node)
    graph.add_node("localization", localization_node)
    graph.add_node("listing_validation", listing_validation_node)
    graph.add_node("risk_review", risk_review_node)
    graph.add_node("await_approval", await_approval_node)
    graph.add_node("complete", complete_node)

    graph.add_edge(START, "product_research")
    graph.add_edge("product_research", "profit_analysis")
    graph.add_edge("profit_analysis", "supplier_evaluation")
    graph.add_edge("supplier_evaluation", "localization")
    graph.add_edge("localization", "listing_validation")
    graph.add_edge("listing_validation", "risk_review")
    graph.add_conditional_edges(
        "risk_review",
        route_after_risk_review,
        {
            "await_approval": "await_approval",
            "complete": "complete",
        },
    )
    graph.add_edge("await_approval", END)
    graph.add_edge("complete", END)
    return graph.compile()


def build_product_launch_publish_graph():
    graph = StateGraph(CommerceAgentState)
    graph.add_node("publish_listing", publish_listing_node)
    graph.add_edge(START, "publish_listing")
    graph.add_edge("publish_listing", END)
    return graph.compile()


def _step_event_metadata(state: CommerceAgentState, step: str) -> dict:
    metadata = {"current_step": str(state["current_step"])}
    if step == "localization":
        listing_versions = state.get("listing_versions", [])
        metadata.update(
            {
                "target_locale": state["target_locale"],
                "localized_listing_count": len(state["localized_listings"]),
                "listing_version_count": len(listing_versions),
                "selected_listing_version_ids": state.get("selected_listing_version_ids", []),
                "listing_version_summary": [
                    listing_version_summary(version) for version in listing_versions
                ],
                "localization_risk_count": len(state["localization_risk_flags"]),
                "marketplaces": [item["marketplace"] for item in state["localized_listings"]],
            }
        )
    return metadata


def _record_completed_step_events(state: CommerceAgentState, steps: list[str] | None = None) -> None:
    selected_steps = steps or state["completed_steps"]
    repo = get_trace_event_repository()
    for step in selected_steps:
        repo.record(
            create_trace_event(
                workflow_id=state["workflow_id"],
                tenant_id=state["tenant_id"],
                agent_role=STEP_AGENT_ROLES.get(step, state["current_agent"]),
                event_type=TraceEventType.NODE_END,
                name=step,
                metadata=_step_event_metadata(state, step),
            )
        )


def _record_tool_call_events(state: CommerceAgentState, only_tool: str | None = None) -> None:
    repo = get_trace_event_repository()
    for tool_call in state["tool_calls"]:
        if only_tool is not None and tool_call.get("tool") != only_tool:
            continue
        repo.record(
            create_trace_event(
                workflow_id=state["workflow_id"],
                tenant_id=state["tenant_id"],
                agent_role=AgentRole(tool_call.get("agent_role", state["current_agent"])),
                event_type=TraceEventType.TOOL_CALL,
                name=str(tool_call.get("tool")),
                metadata=tool_call,
            )
        )


def _record_approval_and_checkpoint_events(state: CommerceAgentState, snapshot_id: str) -> None:
    repo = get_trace_event_repository()
    repo.record(
        create_trace_event(
            workflow_id=state["workflow_id"],
            tenant_id=state["tenant_id"],
            agent_role=AgentRole.SUPERVISOR,
            event_type=TraceEventType.APPROVAL,
            name="approval_requested",
            metadata={
                "approval_request_id": state["approval_request_id"],
                "approval_reasons": state["approval_reasons"],
            },
        )
    )
    repo.record(
        create_trace_event(
            workflow_id=state["workflow_id"],
            tenant_id=state["tenant_id"],
            agent_role=AgentRole.SUPERVISOR,
            event_type=TraceEventType.CHECKPOINT,
            name="snapshot_saved",
            metadata={"snapshot_id": snapshot_id, "checkpoint_name": "await_approval"},
        )
    )


def _record_error_events(state: CommerceAgentState) -> None:
    repo = get_trace_event_repository()
    for error in state["errors"]:
        repo.record(
            create_trace_event(
                workflow_id=state["workflow_id"],
                tenant_id=state["tenant_id"],
                agent_role=state["current_agent"],
                event_type=TraceEventType.ERROR,
                name="workflow_error",
                metadata={"error": error},
            )
        )


def run_product_launch_preview(
    workflow_id: str,
    tenant_id: str,
    product_idea: str,
    target_marketplaces: list[Marketplace],
    target_price: float,
    risk_preference: str,
    target_locale: str = "en-US",
) -> CommerceAgentState:
    initial_state = create_initial_state(
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        current_agent=AgentRole.SUPERVISOR,
        product_idea=product_idea,
        target_marketplaces=[marketplace.value for marketplace in target_marketplaces],
        target_locale=target_locale,
        target_price=target_price,
        risk_preference=risk_preference,
    )
    state = build_product_launch_graph().invoke(initial_state)
    if WorkflowState(state["current_step"]) == WorkflowState.AWAITING_APPROVAL:
        snapshot = get_workflow_snapshot_repository().save(
            workflow_id=state["workflow_id"],
            tenant_id=state["tenant_id"],
            checkpoint_name="await_approval",
            state=state,
        )
        _record_completed_step_events(state)
        _record_tool_call_events(state)
        _record_approval_and_checkpoint_events(state, snapshot.id)
    return state


def run_product_launch_publish_resume(approval_request_id: str | None) -> CommerceAgentState:
    approval = get_approval_repository().get(approval_request_id)
    if approval is None:
        initial_state = create_initial_state(
            workflow_id="unknown",
            tenant_id="unknown",
            current_agent=AgentRole.SUPERVISOR,
        )
        initial_state["approval_request_id"] = approval_request_id
        initial_state["current_step"] = WorkflowState.FAILED
        initial_state["errors"] = ["approval request not found"]
        _record_error_events(initial_state)
        return initial_state

    snapshot = get_workflow_snapshot_repository().get_latest(
        approval.workflow_id,
        tenant_id=approval.tenant_id,
    )
    if snapshot is None:
        initial_state = create_initial_state(
            workflow_id=approval.workflow_id,
            tenant_id=approval.tenant_id,
            current_agent=AgentRole.SUPERVISOR,
        )
        initial_state["approval_request_id"] = approval.id
        initial_state["approval_request"] = approval.model_dump(mode="json")
        initial_state["current_step"] = WorkflowState.FAILED
        initial_state["errors"] = ["workflow snapshot not found"]
        _record_error_events(initial_state)
        return initial_state

    initial_state = snapshot.state
    initial_state["approval_required"] = True
    initial_state["approval_request_id"] = approval.id
    initial_state["approval_request"] = approval.model_dump(mode="json")
    initial_state["approval_reasons"] = approval.reason_codes
    initial_state["risk_level"] = approval.risk_level
    state = build_product_launch_publish_graph().invoke(initial_state)
    if WorkflowState(state["current_step"]) == WorkflowState.FAILED:
        # 多平台发布可能部分成功；失败路径也必须留下已经发生的外部副作用。
        _record_tool_call_events(state, only_tool="publish_listing")
        _record_error_events(state)
    else:
        _record_completed_step_events(state, steps=["publish_listing"])
        _record_tool_call_events(state, only_tool="publish_listing")
    return state
