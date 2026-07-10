from app.adapters.mock_marketplaces import get_mock_adapter
from app.agents.profiles import list_agent_profiles
from app.agents.graphs.state import CommerceAgentState
from app.domain.enums import AgentRole, ApprovalStatus, Marketplace, RiskLevel, WorkflowState
from app.domain.schemas import ListingDraft
from app.repositories.approvals import get_approval_repository
from app.security.boundary import AgentBoundaryPolicy, ToolAccessContext
from app.services.profit import ProfitInput, estimate_profit
from app.services.suppliers import SupplierInput, SupplierScore, score_supplier
from app.tools.registry import build_default_registry


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
    supplier_risk = state["supplier_risk_level"] == "high"
    risk_level = RiskLevel.HIGH if has_invalid_listing or profit_risk == "high" or supplier_risk else RiskLevel.MEDIUM
    approval_reasons = ["publish_listing"]
    if supplier_risk:
        approval_reasons.append("supplier_risk")
    return {
        "current_agent": AgentRole.RISK_REVIEW,
        "current_step": WorkflowState.REVIEWING_RISK,
        "completed_steps": _append_step(state, "risk_review"),
        "risk_level": risk_level,
        "approval_required": True,
        "approval_reasons": approval_reasons,
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
            "target_price": state["target_price"],
        },
    )
    return {
        "current_agent": AgentRole.SUPERVISOR,
        "current_step": WorkflowState.AWAITING_APPROVAL,
        "completed_steps": _append_step(state, "await_approval"),
        "approval_request_id": approval.id,
        "approval_request": approval.model_dump(mode="json"),
    }


def publish_listing_node(state: CommerceAgentState) -> dict:
    approval = get_approval_repository().get(state["approval_request_id"])
    if approval is None:
        return {
            "current_agent": AgentRole.SUPERVISOR,
            "current_step": WorkflowState.FAILED,
            "completed_steps": _append_step(state, "publish_listing"),
            "errors": [*state["errors"], "approval request not found"],
            "publish_results": [],
        }

    if approval.status != ApprovalStatus.APPROVED:
        return {
            "current_agent": AgentRole.SUPERVISOR,
            "current_step": WorkflowState.FAILED,
            "completed_steps": _append_step(state, "publish_listing"),
            "errors": [*state["errors"], "approval is not approved"],
            "approval_request": approval.model_dump(mode="json"),
            "publish_results": [],
        }

    if not state["target_marketplaces"] or state["target_price"] <= 0:
        return {
            "current_agent": AgentRole.SUPERVISOR,
            "current_step": WorkflowState.FAILED,
            "completed_steps": _append_step(state, "publish_listing"),
            "errors": [*state["errors"], "approval metadata is incomplete"],
            "approval_request": approval.model_dump(mode="json"),
            "publish_results": [],
        }

    boundary = AgentBoundaryPolicy(
        profiles=list_agent_profiles(),
        registry=build_default_registry(),
    )
    decision = boundary.evaluate_tool_access(
        ToolAccessContext(
            agent_role=AgentRole.SUPERVISOR,
            tool_name="publish_listing",
            actor_tenant_id=approval.tenant_id,
            target_tenant_id=approval.tenant_id,
            actor_permissions={"listing:publish"},
            approved=True,
            payload={"approval_request_id": approval.id},
        )
    )
    if not decision.allowed:
        return {
            "current_agent": AgentRole.SUPERVISOR,
            "current_step": WorkflowState.FAILED,
            "completed_steps": _append_step(state, "publish_listing"),
            "errors": [*state["errors"], *decision.reasons],
            "approval_request": approval.model_dump(mode="json"),
            "publish_results": [],
        }

    publish_results = []
    tool_calls = [*state["tool_calls"]]
    for marketplace_value in state["target_marketplaces"]:
        marketplace = Marketplace(marketplace_value)
        adapter = get_mock_adapter(marketplace)
        result = adapter.publish_listing(
            _draft_for_marketplace(marketplace, state),
            idempotency_key=f"{approval.id}:{marketplace.value}",
        )
        publish_results.append(result.model_dump(mode="json"))
        tool_calls.append(
            {
                "tool": "publish_listing",
                "marketplace": marketplace.value,
                "risk_level": RiskLevel.HIGH.value,
                "status": "completed",
                "approval_request_id": approval.id,
            }
        )

    return {
        "current_agent": AgentRole.SUPERVISOR,
        "current_step": WorkflowState.COMPLETED,
        "completed_steps": _append_step(state, "publish_listing"),
        "approval_request": approval.model_dump(mode="json"),
        "publish_results": publish_results,
        "tool_calls": tool_calls,
    }


def complete_node(state: CommerceAgentState) -> dict:
    return {
        "current_agent": AgentRole.SUPERVISOR,
        "current_step": WorkflowState.COMPLETED,
        "completed_steps": _append_step(state, "complete"),
    }
