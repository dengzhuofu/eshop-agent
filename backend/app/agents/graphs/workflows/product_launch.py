from langgraph.graph import END, START, StateGraph

from app.agents.graphs.nodes.product_launch import (
    await_approval_node,
    complete_node,
    listing_validation_node,
    publish_listing_node,
    product_research_node,
    profit_analysis_node,
    risk_review_node,
)
from app.agents.graphs.routes.product_launch import route_after_risk_review
from app.agents.graphs.state import CommerceAgentState, create_initial_state
from app.domain.enums import AgentRole, Marketplace, WorkflowState
from app.repositories.approvals import get_approval_repository
from app.repositories.snapshots import get_workflow_snapshot_repository


def build_product_launch_graph():
    graph = StateGraph(CommerceAgentState)
    graph.add_node("product_research", product_research_node)
    graph.add_node("profit_analysis", profit_analysis_node)
    graph.add_node("listing_validation", listing_validation_node)
    graph.add_node("risk_review", risk_review_node)
    graph.add_node("await_approval", await_approval_node)
    graph.add_node("complete", complete_node)

    graph.add_edge(START, "product_research")
    graph.add_edge("product_research", "profit_analysis")
    graph.add_edge("profit_analysis", "listing_validation")
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


def run_product_launch_preview(
    workflow_id: str,
    tenant_id: str,
    product_idea: str,
    target_marketplaces: list[Marketplace],
    target_price: float,
    risk_preference: str,
) -> CommerceAgentState:
    initial_state = create_initial_state(
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        current_agent=AgentRole.SUPERVISOR,
        product_idea=product_idea,
        target_marketplaces=[marketplace.value for marketplace in target_marketplaces],
        target_price=target_price,
        risk_preference=risk_preference,
    )
    state = build_product_launch_graph().invoke(initial_state)
    if WorkflowState(state["current_step"]) == WorkflowState.AWAITING_APPROVAL:
        get_workflow_snapshot_repository().save(
            workflow_id=state["workflow_id"],
            tenant_id=state["tenant_id"],
            checkpoint_name="await_approval",
            state=state,
        )
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
        return initial_state

    initial_state = snapshot.state
    initial_state["approval_required"] = True
    initial_state["approval_request_id"] = approval.id
    initial_state["approval_request"] = approval.model_dump(mode="json")
    initial_state["approval_reasons"] = approval.reason_codes
    initial_state["risk_level"] = approval.risk_level
    return build_product_launch_publish_graph().invoke(initial_state)
