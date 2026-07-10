from pydantic import BaseModel

from app.domain.enums import AgentRole, RiskLevel


class AgentProfile(BaseModel):
    role: AgentRole
    display_name: str
    purpose: str
    allowed_tools: set[str]
    max_risk_level: RiskLevel
    can_request_approval: bool = False
    tenant_scoped: bool = True
    forbidden_data_classes: set[str] = set()


DEFAULT_AGENT_PROFILES = [
    AgentProfile(
        role=AgentRole.SUPERVISOR,
        display_name="Supervisor Agent",
        purpose="Own workflow state, delegate specialist nodes, and request approvals.",
        allowed_tools={
            "search_market_trends",
            "estimate_profit",
            "score_supplier",
            "create_listing_draft",
            "validate_listing",
            "localize_listing",
            "publish_listing",
            "update_price",
            "get_orders",
            "get_order_details",
            "get_shipping_status",
            "get_return_policy",
            "draft_support_response",
            "get_listing_performance",
            "record_evaluation_result",
            "request_refund_approval",
            "issue_refund",
        },
        max_risk_level=RiskLevel.CRITICAL,
        can_request_approval=True,
        forbidden_data_classes={"raw_secret", "unscoped_tenant_data"},
    ),
    AgentProfile(
        role=AgentRole.PRODUCT_RESEARCH,
        display_name="Product Research Agent",
        purpose="Analyze product opportunities using market, competitor, keyword, and review evidence.",
        allowed_tools={"search_market_trends", "record_evaluation_result"},
        max_risk_level=RiskLevel.LOW,
        forbidden_data_classes={"raw_secret", "customer_pii", "payment_data"},
    ),
    AgentProfile(
        role=AgentRole.PROFIT_ANALYST,
        display_name="Profit Analyst Agent",
        purpose="Run deterministic profit, landed-cost, and break-even calculations.",
        allowed_tools={"estimate_profit", "record_evaluation_result"},
        max_risk_level=RiskLevel.LOW,
        forbidden_data_classes={"raw_secret", "customer_pii", "payment_data"},
    ),
    AgentProfile(
        role=AgentRole.SUPPLIER,
        display_name="Supplier Agent",
        purpose="Score suppliers and surface supply-chain risks.",
        allowed_tools={"score_supplier", "record_evaluation_result"},
        max_risk_level=RiskLevel.LOW,
        forbidden_data_classes={"raw_secret", "payment_data"},
    ),
    AgentProfile(
        role=AgentRole.LISTING,
        display_name="Listing Agent",
        purpose="Create and validate marketplace-specific listing drafts.",
        allowed_tools={"create_listing_draft", "validate_listing", "record_evaluation_result"},
        max_risk_level=RiskLevel.MEDIUM,
        forbidden_data_classes={"raw_secret", "payment_data", "customer_pii"},
    ),
    AgentProfile(
        role=AgentRole.LOCALIZATION,
        display_name="Localization Agent",
        purpose="Adapt listing content for locale, units, and policy-sensitive wording.",
        allowed_tools={"localize_listing", "validate_listing", "record_evaluation_result"},
        max_risk_level=RiskLevel.MEDIUM,
        forbidden_data_classes={"raw_secret", "payment_data", "customer_pii"},
    ),
    AgentProfile(
        role=AgentRole.OPS,
        display_name="Operations Agent",
        purpose="Monitor listing performance and propose non-executing optimization actions.",
        allowed_tools={"get_listing_performance", "get_orders", "record_evaluation_result"},
        max_risk_level=RiskLevel.LOW,
        forbidden_data_classes={"raw_secret", "payment_data"},
    ),
    AgentProfile(
        role=AgentRole.CUSTOMER_SUPPORT,
        display_name="Customer Support Agent",
        purpose="Draft grounded customer support responses using order tools and RAG policy evidence.",
        allowed_tools={
            "get_order_details",
            "get_shipping_status",
            "get_return_policy",
            "draft_support_response",
            "request_refund_approval",
            "record_evaluation_result",
        },
        max_risk_level=RiskLevel.HIGH,
        can_request_approval=True,
        forbidden_data_classes={"raw_secret", "full_payment_credentials"},
    ),
    AgentProfile(
        role=AgentRole.RISK_REVIEW,
        display_name="Risk & Review Agent",
        purpose="Evaluate risk, policy compliance, approval needs, and evidence quality.",
        allowed_tools={"validate_listing", "record_evaluation_result", "get_return_policy"},
        max_risk_level=RiskLevel.LOW,
        forbidden_data_classes={"raw_secret", "full_payment_credentials"},
    ),
]


def list_agent_profiles() -> list[AgentProfile]:
    return DEFAULT_AGENT_PROFILES.copy()


def get_agent_profile(role: AgentRole) -> AgentProfile:
    for profile in DEFAULT_AGENT_PROFILES:
        if profile.role == role:
            return profile
    raise KeyError(f"Unknown agent role: {role}")

