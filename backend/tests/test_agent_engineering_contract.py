from app.agents.checkpoints.policy import CheckpointKind, get_checkpoint_policies
from app.agents.evaluation.registry import list_evaluation_scenarios
from app.agents.memory.policy import MemoryScope, get_memory_policies
from app.agents.observability.schema import TraceEventType, create_trace_event
from app.agents.prompts.registry import get_prompt_templates
from app.domain.enums import AgentRole


def test_prompt_templates_are_versioned_and_role_scoped():
    templates = get_prompt_templates()

    listing_prompt = templates["listing_agent_system"]
    support_prompt = templates["customer_support_agent_system"]

    assert listing_prompt.version == "0.1.0"
    assert listing_prompt.owner_agent == AgentRole.LISTING
    assert support_prompt.owner_agent == AgentRole.CUSTOMER_SUPPORT
    assert "secret" in support_prompt.forbidden_context_keys


def test_checkpoint_policies_include_human_approval_interrupt():
    policies = {policy.name: policy for policy in get_checkpoint_policies()}

    assert policies["before_publish_listing"].kind == CheckpointKind.HUMAN_APPROVAL
    assert policies["before_publish_listing"].interrupts_graph is True
    assert policies["after_read_only_research"].interrupts_graph is False


def test_trace_event_schema_preserves_agent_tool_and_tenant_context():
    event = create_trace_event(
        workflow_id="wf_1",
        tenant_id="tenant-a",
        agent_role=AgentRole.LISTING,
        event_type=TraceEventType.TOOL_DECISION,
        name="publish_listing_denied",
        metadata={"reason": "not allowed for agent role"},
    )

    assert event.workflow_id == "wf_1"
    assert event.tenant_id == "tenant-a"
    assert event.agent_role == AgentRole.LISTING
    assert event.event_type == TraceEventType.TOOL_DECISION
    assert event.metadata["reason"] == "not allowed for agent role"


def test_evaluation_scenarios_cover_safety_and_rag_grounding():
    scenarios = {scenario.name: scenario for scenario in list_evaluation_scenarios()}

    assert "listing_claim_safety" in scenarios
    assert "support_rag_groundedness" in scenarios
    assert scenarios["support_rag_groundedness"].requires_citations is True


def test_memory_policies_prevent_cross_tenant_and_secret_storage():
    policies = {policy.name: policy for policy in get_memory_policies()}

    tenant_memory = policies["tenant_workflow_memory"]
    global_memory = policies["global_playbook_memory"]

    assert tenant_memory.scope == MemoryScope.TENANT
    assert tenant_memory.allow_cross_tenant_read is False
    assert "raw_secret" in tenant_memory.forbidden_data_classes
    assert global_memory.scope == MemoryScope.GLOBAL
    assert global_memory.allow_cross_tenant_read is True
