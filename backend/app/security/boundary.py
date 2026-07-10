from pydantic import BaseModel, Field

from app.agents.profiles import AgentProfile
from app.domain.enums import AgentRole, RiskLevel
from app.tools.registry import ToolRegistry

RISK_ORDER = {
    RiskLevel.LOW: 1,
    RiskLevel.MEDIUM: 2,
    RiskLevel.HIGH: 3,
    RiskLevel.CRITICAL: 4,
}

SECRET_KEY_MARKERS = ("api_key", "secret", "token", "password", "credential")


class ToolAccessContext(BaseModel):
    agent_role: AgentRole
    tool_name: str
    actor_tenant_id: str
    target_tenant_id: str
    actor_permissions: set[str]
    approved: bool = False
    payload: dict = Field(default_factory=dict)


class ToolAccessDecision(BaseModel):
    allowed: bool
    reasons: list[str]
    approval_required: bool = False
    can_request_approval: bool = False


class AgentBoundaryPolicy:
    def __init__(self, profiles: list[AgentProfile], registry: ToolRegistry) -> None:
        self._profiles = {profile.role: profile for profile in profiles}
        self._registry = registry

    def evaluate_tool_access(self, context: ToolAccessContext) -> ToolAccessDecision:
        reasons: list[str] = []
        profile = self._profiles.get(context.agent_role)
        if profile is None:
            return ToolAccessDecision(allowed=False, reasons=["unknown agent role"])

        try:
            tool = self._registry.get(context.tool_name)
        except KeyError:
            return ToolAccessDecision(allowed=False, reasons=["unknown tool"])

        if context.tool_name not in profile.allowed_tools:
            reasons.append("not allowed for agent role")

        if profile.tenant_scoped and context.actor_tenant_id != context.target_tenant_id:
            reasons.append("tenant mismatch")

        if tool.required_permission not in context.actor_permissions:
            reasons.append(f"missing permission: {tool.required_permission}")

        if RISK_ORDER[tool.risk_level] > RISK_ORDER[profile.max_risk_level]:
            reasons.append("tool risk exceeds agent max risk")

        if tool.requires_approval and not context.approved:
            reasons.append("approval required")

        reasons.extend(_secret_payload_reasons(context.payload))

        return ToolAccessDecision(
            allowed=not reasons,
            reasons=reasons,
            approval_required=tool.requires_approval,
            can_request_approval=profile.can_request_approval,
        )


def _secret_payload_reasons(payload: dict, prefix: str = "") -> list[str]:
    reasons: list[str] = []
    for key, value in payload.items():
        key_path = f"{prefix}.{key}" if prefix else str(key)
        lower_key = str(key).lower()
        if any(marker in lower_key for marker in SECRET_KEY_MARKERS):
            reasons.append(f"secret-like payload key: {key_path}")
        if isinstance(value, dict):
            reasons.extend(_secret_payload_reasons(value, key_path))
    return reasons

