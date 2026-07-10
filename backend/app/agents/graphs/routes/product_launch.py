from app.agents.graphs.state import CommerceAgentState


def route_after_risk_review(state: CommerceAgentState) -> str:
    if state["approval_required"]:
        return "await_approval"
    return "complete"

