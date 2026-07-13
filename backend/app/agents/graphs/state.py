from typing import Any, TypedDict

from app.domain.enums import AgentRole, RiskLevel


class CommerceAgentState(TypedDict):
    workflow_id: str
    tenant_id: str
    current_agent: AgentRole
    current_step: str
    product_idea: str
    target_marketplaces: list[str]
    target_locale: str
    target_price: float
    risk_preference: str
    messages: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]
    approval_required: bool
    approval_request_id: str | None
    approval_request: dict[str, Any]
    approval_reasons: list[str]
    risk_level: RiskLevel
    evidence: list[dict[str, Any]]
    profit_estimate: dict[str, Any]
    supplier_evaluations: list[dict[str, Any]]
    selected_supplier_id: str | None
    supplier_risk_level: str
    listing_drafts: list[dict[str, Any]]
    localized_listings: list[dict[str, Any]]
    listing_versions: list[dict[str, Any]]
    selected_listing_version_ids: list[str]
    approved_listing_version_ids: list[str]
    localization_risk_flags: list[dict[str, Any]]
    listing_validations: list[dict[str, Any]]
    publish_results: list[dict[str, Any]]
    completed_steps: list[str]
    errors: list[str]


def create_initial_state(
    workflow_id: str,
    tenant_id: str,
    current_agent: AgentRole,
    product_idea: str = "",
    target_marketplaces: list[str] | None = None,
    target_locale: str = "en-US",
    target_price: float = 0,
    risk_preference: str = "balanced",
) -> CommerceAgentState:
    return {
        "workflow_id": workflow_id,
        "tenant_id": tenant_id,
        "current_agent": current_agent,
        "current_step": "queued",
        "product_idea": product_idea,
        "target_marketplaces": target_marketplaces or [],
        "target_locale": target_locale,
        "target_price": target_price,
        "risk_preference": risk_preference,
        "messages": [],
        "tool_calls": [],
        "approval_required": False,
        "approval_request_id": None,
        "approval_request": {},
        "approval_reasons": [],
        "risk_level": RiskLevel.LOW,
        "evidence": [],
        "profit_estimate": {},
        "supplier_evaluations": [],
        "selected_supplier_id": None,
        "supplier_risk_level": "unknown",
        "listing_drafts": [],
        "localized_listings": [],
        "listing_versions": [],
        "selected_listing_version_ids": [],
        "approved_listing_version_ids": [],
        "localization_risk_flags": [],
        "listing_validations": [],
        "publish_results": [],
        "completed_steps": [],
        "errors": [],
    }
