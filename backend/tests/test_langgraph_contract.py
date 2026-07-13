from app.agents.graphs.nodes.base import NodeSideEffect, get_node_contracts
from app.agents.graphs.routes.base import RouteName, choose_approval_route
from app.agents.graphs.state import create_initial_state
from app.agents.mcp.registry import list_mcp_connectors
from app.agents.skills.registry import list_agent_skills
from app.domain.enums import AgentRole, RiskLevel


def test_initial_langgraph_state_contains_required_agent_fields():
    state = create_initial_state(
        workflow_id="wf_1",
        tenant_id="tenant-a",
        current_agent=AgentRole.SUPERVISOR,
    )

    assert state["workflow_id"] == "wf_1"
    assert state["tenant_id"] == "tenant-a"
    assert state["current_agent"] == AgentRole.SUPERVISOR
    assert state["messages"] == []
    assert state["tool_calls"] == []
    assert state["approval_required"] is False
    assert state["risk_level"] == RiskLevel.LOW
    assert state["target_locale"] == "en-US"
    assert state["listing_drafts"] == []
    assert state["localized_listings"] == []
    assert state["localization_risk_flags"] == []


def test_node_contracts_separate_read_only_and_approval_gated_nodes():
    contracts = {contract.name: contract for contract in get_node_contracts()}

    assert contracts["product_research"].side_effect == NodeSideEffect.READ_ONLY
    assert contracts["profit_analysis"].side_effect == NodeSideEffect.DETERMINISTIC
    assert contracts["listing_validation"].owner_agent == AgentRole.LISTING
    assert {"listing_validations", "tool_calls"}.issubset(contracts["listing_validation"].output_keys)
    assert contracts["publish_listing"].side_effect == NodeSideEffect.APPROVAL_GATED
    assert {
        "supplier_evaluations",
        "selected_supplier_id",
        "supplier_risk_level",
    }.issubset(contracts["supplier_evaluation"].output_keys)
    assert contracts["localization"].owner_agent == AgentRole.LOCALIZATION
    assert contracts["localization"].side_effect == NodeSideEffect.DETERMINISTIC
    assert {
        "listing_drafts",
        "localized_listings",
        "localization_risk_flags",
        "tool_calls",
        "evidence",
    }.issubset(contracts["localization"].output_keys)


def test_approval_route_does_not_execute_side_effects():
    state = create_initial_state(
        workflow_id="wf_1",
        tenant_id="tenant-a",
        current_agent=AgentRole.SUPERVISOR,
    )
    state["approval_required"] = True

    decision = choose_approval_route(state)

    assert decision.name == RouteName.AWAIT_APPROVAL
    assert decision.next_node == "await_approval"
    assert decision.executes_side_effect is False


def test_mcp_connector_registry_stores_secret_references_not_secret_values():
    connectors = list_mcp_connectors()

    assert connectors
    assert all(connector.secret_env_vars for connector in connectors)
    assert all("sk-" not in value for connector in connectors for value in connector.secret_env_vars)


def test_agent_skill_registry_has_domain_scoped_skills():
    skills = {skill.name: skill for skill in list_agent_skills()}

    assert "cross_border_listing_policy" in skills
    assert "customer_support_rag_policy" in skills
    assert skills["customer_support_rag_policy"].allowed_agents == {AgentRole.CUSTOMER_SUPPORT}
