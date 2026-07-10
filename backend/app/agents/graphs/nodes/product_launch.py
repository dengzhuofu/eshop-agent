from app.adapters.mock_marketplaces import get_mock_adapter
from app.agents.graphs.state import CommerceAgentState
from app.domain.enums import AgentRole, Marketplace, RiskLevel, WorkflowState
from app.domain.schemas import ListingDraft
from app.repositories.approvals import get_approval_repository
from app.services.profit import ProfitInput, estimate_profit


def _append_step(state: CommerceAgentState, step: str) -> list[str]:
    return [*state["completed_steps"], step]


def product_research_node(state: CommerceAgentState) -> dict:
    return {
        "current_agent": AgentRole.PRODUCT_RESEARCH,
        "current_step": WorkflowState.RESEARCHING,
        "completed_steps": _append_step(state, "product_research"),
        "evidence": [
            *state["evidence"],
            {
                "source": "mock_market_trends",
                "summary": f"Storage demand signal found for {state['product_idea']}.",
                "confidence": 0.82,
            },
        ],
        "messages": [
            *state["messages"],
            {
                "agent": AgentRole.PRODUCT_RESEARCH.value,
                "content": "Found mock demand and review-pain evidence for launch preview.",
            },
        ],
    }


def profit_analysis_node(state: CommerceAgentState) -> dict:
    profit = estimate_profit(
        ProfitInput(
            unit_cost=8.0,
            shipping_cost=4.0,
            duty_rate=0.1,
            marketplace_fee_rate=0.15,
            payment_fee_rate=0.03,
            fulfillment_fee=3.0,
            ad_cost_per_unit=2.0,
            return_rate=0.05,
            target_price=state["target_price"],
        )
    )
    return {
        "current_agent": AgentRole.PROFIT_ANALYST,
        "current_step": WorkflowState.ANALYZING_PROFIT,
        "completed_steps": _append_step(state, "profit_analysis"),
        "profit_estimate": profit.model_dump(),
        "tool_calls": [
            *state["tool_calls"],
            {
                "tool": "estimate_profit",
                "risk_level": RiskLevel.LOW.value,
                "status": "completed",
            },
        ],
    }


def _draft_for_marketplace(marketplace: Marketplace, state: CommerceAgentState) -> ListingDraft:
    attributes: dict[str, str | int | float | bool] = {"category": "home_storage"}
    if marketplace == Marketplace.SHOPIFY:
        attributes["seo_title"] = "Under-bed organizer"
    if marketplace == Marketplace.TIKTOK_SHOP:
        attributes["video_hook"] = "Transform your room"

    return ListingDraft(
        marketplace=marketplace,
        sku=f"SKU-{marketplace.value.upper()}-001",
        title="Foldable under-bed storage organizer",
        description=f"Launch preview for {state['product_idea']}.",
        bullet_points=["Fits under beds", "Foldable fabric body", "Easy seasonal storage"],
        price=state["target_price"],
        attributes=attributes,
    )


def listing_validation_node(state: CommerceAgentState) -> dict:
    validations = []
    tool_calls = [*state["tool_calls"]]
    for marketplace_value in state["target_marketplaces"]:
        marketplace = Marketplace(marketplace_value)
        adapter = get_mock_adapter(marketplace)
        validation = adapter.validate_listing(_draft_for_marketplace(marketplace, state))
        validations.append(
            {
                "marketplace": marketplace.value,
                "valid": validation.valid,
                "issues": [issue.model_dump(mode="json") for issue in validation.issues],
            }
        )
        tool_calls.append(
            {
                "tool": "validate_listing",
                "marketplace": marketplace.value,
                "risk_level": RiskLevel.LOW.value,
                "status": "completed",
            }
        )

    return {
        "current_agent": AgentRole.LISTING,
        "current_step": WorkflowState.DRAFTING_LISTINGS,
        "completed_steps": _append_step(state, "listing_validation"),
        "listing_validations": validations,
        "tool_calls": tool_calls,
    }


def risk_review_node(state: CommerceAgentState) -> dict:
    has_invalid_listing = any(not item["valid"] for item in state["listing_validations"])
    profit_risk = state["profit_estimate"].get("profit_risk")
    risk_level = RiskLevel.HIGH if has_invalid_listing or profit_risk == "high" else RiskLevel.MEDIUM
    return {
        "current_agent": AgentRole.RISK_REVIEW,
        "current_step": WorkflowState.REVIEWING_RISK,
        "completed_steps": _append_step(state, "risk_review"),
        "risk_level": risk_level,
        "approval_required": True,
        "approval_reasons": ["publish_listing"],
    }


def await_approval_node(state: CommerceAgentState) -> dict:
    approval_id = f"appr_{state['workflow_id']}"
    approval = get_approval_repository().upsert_pending(
        approval_id=approval_id,
        workflow_id=state["workflow_id"],
        tenant_id=state["tenant_id"],
        requested_by=AgentRole.SUPERVISOR.value,
        reason_codes=state["approval_reasons"],
        risk_level=state["risk_level"],
        resource_type="workflow",
        resource_id=state["workflow_id"],
        metadata={
            "tool": "publish_listing",
            "product_idea": state["product_idea"],
            "target_marketplaces": state["target_marketplaces"],
        },
    )
    return {
        "current_agent": AgentRole.SUPERVISOR,
        "current_step": WorkflowState.AWAITING_APPROVAL,
        "completed_steps": _append_step(state, "await_approval"),
        "approval_request_id": approval.id,
        "approval_request": approval.model_dump(mode="json"),
    }


def complete_node(state: CommerceAgentState) -> dict:
    return {
        "current_agent": AgentRole.SUPERVISOR,
        "current_step": WorkflowState.COMPLETED,
        "completed_steps": _append_step(state, "complete"),
    }
