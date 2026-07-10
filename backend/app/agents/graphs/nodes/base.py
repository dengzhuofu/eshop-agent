from enum import StrEnum

from pydantic import BaseModel

from app.domain.enums import AgentRole


class NodeSideEffect(StrEnum):
    READ_ONLY = "read_only"
    DETERMINISTIC = "deterministic"
    APPROVAL_GATED = "approval_gated"


class NodeContract(BaseModel):
    name: str
    owner_agent: AgentRole
    side_effect: NodeSideEffect
    output_keys: set[str]


def get_node_contracts() -> list[NodeContract]:
    return [
        NodeContract(
            name="product_research",
            owner_agent=AgentRole.PRODUCT_RESEARCH,
            side_effect=NodeSideEffect.READ_ONLY,
            output_keys={"evidence", "messages"},
        ),
        NodeContract(
            name="profit_analysis",
            owner_agent=AgentRole.PROFIT_ANALYST,
            side_effect=NodeSideEffect.DETERMINISTIC,
            output_keys={"tool_calls", "risk_level"},
        ),
        NodeContract(
            name="supplier_evaluation",
            owner_agent=AgentRole.SUPPLIER,
            side_effect=NodeSideEffect.DETERMINISTIC,
            output_keys={
                "tool_calls",
                "evidence",
                "supplier_evaluations",
                "selected_supplier_id",
                "supplier_risk_level",
            },
        ),
        NodeContract(
            name="listing_draft",
            owner_agent=AgentRole.LISTING,
            side_effect=NodeSideEffect.DETERMINISTIC,
            output_keys={"messages", "tool_calls"},
        ),
        NodeContract(
            name="risk_review",
            owner_agent=AgentRole.RISK_REVIEW,
            side_effect=NodeSideEffect.DETERMINISTIC,
            output_keys={"risk_level", "approval_required"},
        ),
        NodeContract(
            name="publish_listing",
            owner_agent=AgentRole.SUPERVISOR,
            side_effect=NodeSideEffect.APPROVAL_GATED,
            output_keys={"tool_calls"},
        ),
    ]
