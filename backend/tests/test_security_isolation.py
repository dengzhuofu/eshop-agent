from app.agents.profiles import list_agent_profiles
from app.domain.enums import AgentRole
from app.security.boundary import AgentBoundaryPolicy, ToolAccessContext
from app.tools.registry import build_default_registry


def _policy() -> AgentBoundaryPolicy:
    return AgentBoundaryPolicy(
        profiles=list_agent_profiles(),
        registry=build_default_registry(),
    )


def test_cross_tenant_tool_access_is_denied():
    decision = _policy().evaluate_tool_access(
        ToolAccessContext(
            agent_role=AgentRole.PRODUCT_RESEARCH,
            tool_name="search_market_trends",
            actor_tenant_id="tenant-a",
            target_tenant_id="tenant-b",
            actor_permissions={"workflow:read"},
        )
    )

    assert decision.allowed is False
    assert "tenant mismatch" in decision.reasons


def test_high_risk_tool_requires_approval_even_with_permission():
    decision = _policy().evaluate_tool_access(
        ToolAccessContext(
            agent_role=AgentRole.SUPERVISOR,
            tool_name="publish_listing",
            actor_tenant_id="tenant-a",
            target_tenant_id="tenant-a",
            actor_permissions={"listing:publish"},
            approved=False,
        )
    )

    assert decision.allowed is False
    assert decision.approval_required is True
    assert decision.can_request_approval is True
    assert "approval required" in decision.reasons


def test_approved_high_risk_tool_with_permission_is_allowed_for_supervisor():
    decision = _policy().evaluate_tool_access(
        ToolAccessContext(
            agent_role=AgentRole.SUPERVISOR,
            tool_name="publish_listing",
            actor_tenant_id="tenant-a",
            target_tenant_id="tenant-a",
            actor_permissions={"listing:publish"},
            approved=True,
        )
    )

    assert decision.allowed is True
    assert decision.approval_required is True


def test_missing_permission_is_denied():
    decision = _policy().evaluate_tool_access(
        ToolAccessContext(
            agent_role=AgentRole.PROFIT_ANALYST,
            tool_name="estimate_profit",
            actor_tenant_id="tenant-a",
            target_tenant_id="tenant-a",
            actor_permissions=set(),
        )
    )

    assert decision.allowed is False
    assert "missing permission: workflow:read" in decision.reasons


def test_secret_like_payload_is_denied_before_llm_context_exposure():
    decision = _policy().evaluate_tool_access(
        ToolAccessContext(
            agent_role=AgentRole.PRODUCT_RESEARCH,
            tool_name="search_market_trends",
            actor_tenant_id="tenant-a",
            target_tenant_id="tenant-a",
            actor_permissions={"workflow:read"},
            payload={"api_key": "sk-real-secret"},
        )
    )

    assert decision.allowed is False
    assert "secret-like payload key: api_key" in decision.reasons

