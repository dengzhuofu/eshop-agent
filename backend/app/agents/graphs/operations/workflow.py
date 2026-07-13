from datetime import datetime
from functools import partial

from langgraph.graph import END, START, StateGraph

from app.adapters.operations import OperationsReadPort, get_seeded_operations_read_port
from app.agents.graphs.operations.nodes import (
    complete_node,
    detect_anomalies_node,
    load_operations_node,
    propose_actions_node,
    route_node,
)
from app.agents.graphs.operations.routes import route_after_load
from app.agents.graphs.operations.state import (
    OpsAgentState,
    create_initial_operations_state,
)
from app.domain.enums import Marketplace
from app.domain.operations import OperationsReadQuery


def build_operations_graph(port: OperationsReadPort):
    graph = StateGraph(OpsAgentState)
    graph.add_node("load_operations", partial(load_operations_node, port=port))
    graph.add_node("route", route_node)
    graph.add_node("detect_anomalies", detect_anomalies_node)
    graph.add_node("propose_actions", propose_actions_node)
    graph.add_node("complete", complete_node)

    graph.add_edge(START, "load_operations")
    graph.add_edge("load_operations", "route")
    graph.add_conditional_edges(
        "route",
        route_after_load,
        {
            "detect_anomalies": "detect_anomalies",
            "complete": "complete",
        },
    )
    graph.add_edge("detect_anomalies", "propose_actions")
    graph.add_edge("propose_actions", "complete")
    graph.add_edge("complete", END)
    return graph.compile()


def run_operations_agent(
    *,
    workflow_id: str,
    tenant_id: str,
    as_of: datetime,
    marketplaces: list[Marketplace] | None = None,
    listing_version_ids: list[str] | None = None,
    port: OperationsReadPort | None = None,
) -> OpsAgentState:
    query = OperationsReadQuery(
        tenant_id=tenant_id,
        as_of=as_of,
        marketplaces=marketplaces,
        listing_version_ids=listing_version_ids,
    )
    initial_state = create_initial_operations_state(
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        query=query,
    )
    selected_port = port if port is not None else get_seeded_operations_read_port()
    return build_operations_graph(selected_port).invoke(initial_state)
