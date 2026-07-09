from pydantic import BaseModel

from app.domain.enums import RiskLevel


class ToolDefinition(BaseModel):
    name: str
    description: str
    risk_level: RiskLevel
    required_permission: str
    requires_approval: bool
    idempotent: bool = False


class ToolRegistry:
    def __init__(self, tools: list[ToolDefinition]) -> None:
        self._tools = {tool.name: tool for tool in tools}

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
            ),
            ToolDefinition(
                name="create_listing_draft",
                description="Create marketplace-specific listing draft content.",
                risk_level=RiskLevel.MEDIUM,
                required_permission="workflow:create",
                requires_approval=False,
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
                name="issue_refund",
                description="Issue a customer refund.",
                risk_level=RiskLevel.CRITICAL,
                required_permission="refund:issue",
                requires_approval=True,
                idempotent=True,
            ),
        ]
    )

