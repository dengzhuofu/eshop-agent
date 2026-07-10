from enum import StrEnum

from pydantic import BaseModel

from app.agents.graphs.state import CommerceAgentState


class RouteName(StrEnum):
    CONTINUE = "continue"
    AWAIT_APPROVAL = "await_approval"
    RETRY = "retry"
    FAIL = "fail"
    COMPLETE = "complete"


class RouteDecision(BaseModel):
    name: RouteName
    next_node: str
    executes_side_effect: bool = False


def choose_approval_route(state: CommerceAgentState) -> RouteDecision:
    if state["approval_required"]:
        return RouteDecision(
            name=RouteName.AWAIT_APPROVAL,
            next_node="await_approval",
            executes_side_effect=False,
        )
    return RouteDecision(
        name=RouteName.CONTINUE,
        next_node="execute_next",
        executes_side_effect=False,
    )

