from enum import StrEnum


class Marketplace(StrEnum):
    AMAZON = "amazon"
    SHOPIFY = "shopify"
    TIKTOK_SHOP = "tiktok_shop"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkflowState(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    RESEARCHING = "researching"
    ANALYZING_PROFIT = "analyzing_profit"
    EVALUATING_SUPPLIERS = "evaluating_suppliers"
    DRAFTING_LISTINGS = "drafting_listings"
    LOCALIZING = "localizing"
    REVIEWING_RISK = "reviewing_risk"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    MONITORING = "monitoring"
    HANDLING_SUPPORT = "handling_support"
    RETROSPECTIVE = "retrospective"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApprovalStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AgentRole(StrEnum):
    SUPERVISOR = "supervisor"
    PRODUCT_RESEARCH = "product_research"
    PROFIT_ANALYST = "profit_analyst"
    SUPPLIER = "supplier"
    LISTING = "listing"
    LOCALIZATION = "localization"
    OPS = "ops"
    CUSTOMER_SUPPORT = "customer_support"
    RISK_REVIEW = "risk_review"
