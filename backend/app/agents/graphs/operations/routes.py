from typing import Literal

from app.agents.graphs.operations.state import OpsAgentState


def route_after_load(state: OpsAgentState) -> Literal["detect_anomalies", "complete"]:
    if state["route_decision"] == "analyze":
        return "detect_anomalies"
    return "complete"
