from langgraph.graph import END, START, StateGraph

from app.agents.graphs.nodes.product_launch import (
    await_approval_node,
    complete_node,
    listing_validation_node,
    product_research_node,
    profit_analysis_node,
    risk_review_node,
)
from app.agents.graphs.routes.product_launch import route_after_risk_review
from app.agents.graphs.state import CommerceAgentState, create_initial_state
from app.domain.enums import AgentRole, Marketplace


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
    return build_product_launch_graph().invoke(initial_state)
