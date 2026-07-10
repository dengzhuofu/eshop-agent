from app.agents.profiles import get_agent_profile, list_agent_profiles
from app.domain.enums import AgentRole, RiskLevel
from app.security.boundary import AgentBoundaryPolicy, ToolAccessContext
from app.tools.registry import build_default_registry


def test_all_agent_profiles_only_reference_registered_tools():
    registry = build_default_registry()
    registered_tool_names = {tool.name for tool in registry.list()}

    for profile in list_agent_profiles():
        assert profile.allowed_tools <= registered_tool_names


def test_listing_agent_can_draft_and_validate_but_cannot_publish():
    policy = AgentBoundaryPolicy(
        profiles=list_agent_profiles(),
        registry=build_default_registry(),
    )
    allowed_context = ToolAccessContext(
        agent_role=AgentRole.LISTING,
        tool_name="create_listing_draft",
        actor_tenant_id="tenant-a",
        target_tenant_id="tenant-a",
        actor_permissions={"workflow:create"},
    )
    denied_context = ToolAccessContext(
        agent_role=AgentRole.LISTING,
        tool_name="publish_listing",
        actor_tenant_id="tenant-a",
        target_tenant_id="tenant-a",
        actor_permissions={"listing:publish"},
        approved=True,
    )

    allowed = policy.evaluate_tool_access(allowed_context)
    denied = policy.evaluate_tool_access(denied_context)

    assert allowed.allowed is True
    assert denied.allowed is False
    assert "not allowed for agent role" in denied.reasons


def test_customer_support_agent_can_draft_response_but_cannot_issue_refund():
    policy = AgentBoundaryPolicy(
        profiles=list_agent_profiles(),
        registry=build_default_registry(),
    )
    allowed_context = ToolAccessContext(
        agent_role=AgentRole.CUSTOMER_SUPPORT,
        tool_name="draft_support_response",
        actor_tenant_id="tenant-a",
        target_tenant_id="tenant-a",
        actor_permissions={"support:respond"},
    )
    denied_context = ToolAccessContext(
        agent_role=AgentRole.CUSTOMER_SUPPORT,
        tool_name="issue_refund",
        actor_tenant_id="tenant-a",
        target_tenant_id="tenant-a",
        actor_permissions={"refund:issue"},
        approved=True,
    )

    allowed = policy.evaluate_tool_access(allowed_context)
    denied = policy.evaluate_tool_access(denied_context)

    assert allowed.allowed is True
    assert denied.allowed is False
    assert "not allowed for agent role" in denied.reasons


def test_supervisor_profile_can_request_high_risk_approval():
    profile = get_agent_profile(AgentRole.SUPERVISOR)

    assert profile.can_request_approval is True
    assert profile.max_risk_level == RiskLevel.CRITICAL
    assert "publish_listing" in profile.allowed_tools

