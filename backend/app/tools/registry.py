from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import RiskLevel
from app.domain.schemas import ListingDraft, ValidationResult
from app.services.profit import ProfitEstimate, ProfitInput
from app.services.suppliers import SupplierInput, SupplierScore
from app.tools.schemas import RetryPolicy


def _no_retry_policy() -> RetryPolicy:
    return RetryPolicy(
        max_attempts=1,
        initial_backoff_seconds=0,
        backoff_multiplier=1,
        max_backoff_seconds=0,
        retry_on=frozenset(),
    )


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    risk_level: RiskLevel
    required_permission: str
    requires_approval: bool
    idempotent: bool = False
    version: str = "1.0.0"
    input_model: type[BaseModel] | None = None
    output_model: type[BaseModel] | None = None
    timeout_seconds: float = Field(default=5.0, gt=0)
    retry_policy: RetryPolicy = Field(default_factory=_no_retry_policy)
    audit_policy: Literal["metadata_only"] = "metadata_only"


class ToolRegistry:
    def __init__(self, tools: list[ToolDefinition]) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        for tool in tools:
            if tool.name in self._tools:
                raise ValueError(f"Duplicate tool name: {tool.name}")
            self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Unknown tool: {name}") from exc

    def list(self) -> list[ToolDefinition]:
        return list(self._tools.values())


def build_default_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            ToolDefinition(
                name="search_market_trends",
                description="Read market trend records for a product idea.",
                risk_level=RiskLevel.LOW,
                required_permission="workflow:read",
                requires_approval=False,
            ),
            ToolDefinition(
                name="estimate_profit",
                description="Run deterministic landed-cost and margin calculation.",
                risk_level=RiskLevel.LOW,
                required_permission="workflow:read",
                requires_approval=False,
                input_model=ProfitInput,
                output_model=ProfitEstimate,
            ),
            ToolDefinition(
                name="create_listing_draft",
                description="Create marketplace-specific listing draft content.",
                risk_level=RiskLevel.MEDIUM,
                required_permission="workflow:create",
                requires_approval=False,
            ),
            ToolDefinition(
                name="validate_listing",
                description="Validate a listing draft against marketplace rules.",
                risk_level=RiskLevel.LOW,
                required_permission="workflow:read",
                requires_approval=False,
                input_model=ListingDraft,
                output_model=ValidationResult,
            ),
            ToolDefinition(
                name="localize_listing",
                description="Localize listing content for a target locale.",
                risk_level=RiskLevel.MEDIUM,
                required_permission="workflow:create",
                requires_approval=False,
            ),
            ToolDefinition(
                name="score_supplier",
                description="Run deterministic supplier scoring.",
                risk_level=RiskLevel.LOW,
                required_permission="workflow:read",
                requires_approval=False,
                input_model=SupplierInput,
                output_model=SupplierScore,
            ),
            ToolDefinition(
                name="publish_listing",
                description="Publish a listing through a marketplace adapter.",
                risk_level=RiskLevel.HIGH,
                required_permission="listing:publish",
                requires_approval=True,
                idempotent=True,
            ),
            ToolDefinition(
                name="update_price",
                description="Update marketplace listing price.",
                risk_level=RiskLevel.HIGH,
                required_permission="price:update",
                requires_approval=True,
                idempotent=True,
            ),
            ToolDefinition(
                name="get_orders",
                description="Read marketplace orders for support or operations workflows.",
                risk_level=RiskLevel.LOW,
                required_permission="workflow:read",
                requires_approval=False,
            ),
            ToolDefinition(
                name="get_order_details",
                description="Read order details for support workflows.",
                risk_level=RiskLevel.LOW,
                required_permission="workflow:read",
                requires_approval=False,
            ),
            ToolDefinition(
                name="get_shipping_status",
                description="Read shipping status for support workflows.",
                risk_level=RiskLevel.LOW,
                required_permission="workflow:read",
                requires_approval=False,
            ),
            ToolDefinition(
                name="get_return_policy",
                description="Retrieve tenant and marketplace return policy references.",
                risk_level=RiskLevel.LOW,
                required_permission="workflow:read",
                requires_approval=False,
            ),
            ToolDefinition(
                name="draft_support_response",
                description="Draft a grounded support response without sending it.",
                risk_level=RiskLevel.MEDIUM,
                required_permission="support:respond",
                requires_approval=False,
            ),
            ToolDefinition(
                name="get_listing_performance",
                description="Read mock listing performance metrics.",
                risk_level=RiskLevel.LOW,
                required_permission="workflow:read",
                requires_approval=False,
            ),
            ToolDefinition(
                name="record_evaluation_result",
                description="Record evaluation output for a workflow step.",
                risk_level=RiskLevel.LOW,
                required_permission="observability:read",
                requires_approval=False,
            ),
            ToolDefinition(
                name="request_refund_approval",
                description="Create a refund approval request without issuing money movement.",
                risk_level=RiskLevel.HIGH,
                required_permission="approval:review",
                requires_approval=True,
                idempotent=True,
            ),
            ToolDefinition(
                name="issue_refund",
                description="Issue a customer refund.",
                risk_level=RiskLevel.CRITICAL,
                required_permission="refund:issue",
                requires_approval=True,
                idempotent=True,
            ),
        ]
    )
