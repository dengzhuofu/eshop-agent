from app.agents.graphs.state import CommerceAgentState
from app.domain.enums import AgentRole, RiskLevel, WorkflowState
from app.services.profit import ProfitInput, estimate_profit
from app.services.suppliers import SupplierInput, SupplierScore, score_supplier


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
                "agent_role": AgentRole.PROFIT_ANALYST.value,
                "risk_level": RiskLevel.LOW.value,
                "status": "completed",
            },
        ],
    }


def _supplier_candidates(state: CommerceAgentState) -> list[SupplierInput]:
    if state["risk_preference"] == "supplier_risk":
        return [
            SupplierInput(
                supplier_id="SUP-RISK-1",
                unit_price=7.5,
                moq=1200,
                lead_time_days=45,
                quality_score=0.68,
                defect_rate=0.12,
                response_time_hours=48,
                has_required_certifications=False,
            )
        ]

    return [
        SupplierInput(
            supplier_id="SUP-1",
            unit_price=8.0,
            moq=300,
            lead_time_days=14,
            quality_score=0.92,
            defect_rate=0.02,
            response_time_hours=8,
            has_required_certifications=True,
        ),
        SupplierInput(
            supplier_id="SUP-2",
            unit_price=7.5,
            moq=1200,
            lead_time_days=45,
            quality_score=0.68,
            defect_rate=0.12,
            response_time_hours=48,
            has_required_certifications=False,
        ),
    ]


def _select_supplier(scores: list[SupplierScore]) -> SupplierScore | None:
    recommended = [score for score in scores if score.recommended]
    candidates = recommended or scores
    if not candidates:
        return None
    return max(candidates, key=lambda score: score.total_score)


def supplier_evaluation_node(state: CommerceAgentState) -> dict:
    scores = [score_supplier(candidate) for candidate in _supplier_candidates(state)]
    selected = _select_supplier(scores)
    supplier_risk_level = selected.risk_level if selected is not None and selected.recommended else "high"

    return {
        "current_agent": AgentRole.SUPPLIER,
        "current_step": WorkflowState.EVALUATING_SUPPLIERS,
        "completed_steps": _append_step(state, "supplier_evaluation"),
        "supplier_evaluations": [score.model_dump() for score in scores],
        "selected_supplier_id": selected.supplier_id if selected is not None and selected.recommended else None,
        "supplier_risk_level": supplier_risk_level,
        "tool_calls": [
            *state["tool_calls"],
            *[
                {
                    "tool": "score_supplier",
                    "agent_role": AgentRole.SUPPLIER.value,
                    "supplier_id": score.supplier_id,
                    "risk_level": RiskLevel.LOW.value,
                    "status": "completed",
                }
                for score in scores
            ],
        ],
        "evidence": [
            *state["evidence"],
            {
                "source": "mock_supplier_scorecard",
                "summary": (
                    f"Selected supplier {selected.supplier_id}"
                    if selected is not None and selected.recommended
                    else "No low-risk supplier selected"
                ),
                "confidence": 0.86,
            },
        ],
    }


def risk_review_node(state: CommerceAgentState) -> dict:
    has_invalid_listing = any(not item["valid"] for item in state["listing_validations"])
    profit_risk = state["profit_estimate"].get("profit_risk")
    supplier_risk = state["supplier_risk_level"] == "high"
    localization_risk = any(
        flag.get("risk_level") in {RiskLevel.HIGH.value, RiskLevel.CRITICAL.value}
        for flag in state["localization_risk_flags"]
    )
    risk_level = (
        RiskLevel.HIGH
        if has_invalid_listing or profit_risk == "high" or supplier_risk or localization_risk
        else RiskLevel.MEDIUM
    )
    approval_reasons = ["publish_listing"]
    if supplier_risk:
        approval_reasons.append("supplier_risk")
    if localization_risk:
        approval_reasons.append("localization_risk")
    return {
        "current_agent": AgentRole.RISK_REVIEW,
        "current_step": WorkflowState.REVIEWING_RISK,
        "completed_steps": _append_step(state, "risk_review"),
        "risk_level": risk_level,
        "approval_required": True,
        "approval_reasons": approval_reasons,
    }


def complete_node(state: CommerceAgentState) -> dict:
    return {
        "current_agent": AgentRole.SUPERVISOR,
        "current_step": WorkflowState.COMPLETED,
        "completed_steps": _append_step(state, "complete"),
    }
