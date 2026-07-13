from app.agents.graphs.workflows.product_launch import (
    run_product_launch_preview,
    run_product_launch_publish_resume,
)
from app.agents.observability.schema import TraceEventType
from app.domain.enums import AgentRole, Marketplace, RiskLevel, WorkflowState
from app.repositories.approvals import get_approval_repository
from app.repositories.events import get_trace_event_repository
from app.repositories.snapshots import get_workflow_snapshot_repository


def test_product_launch_graph_routes_to_awaiting_approval():
    state = run_product_launch_preview(
        workflow_id="wf_test",
        tenant_id="tenant-a",
        product_idea="foldable under-bed storage organizer",
        target_marketplaces=[
            Marketplace.AMAZON,
            Marketplace.SHOPIFY,
            Marketplace.TIKTOK_SHOP,
        ],
        target_price=29.99,
        risk_preference="balanced",
    )

    assert state["current_step"] == WorkflowState.AWAITING_APPROVAL
    assert state["approval_required"] is True
    assert state["approval_reasons"] == ["publish_listing"]


def test_product_launch_graph_records_ordered_steps_and_evidence():
    state = run_product_launch_preview(
        workflow_id="wf_test",
        tenant_id="tenant-a",
        product_idea="foldable under-bed storage organizer",
        target_marketplaces=[Marketplace.AMAZON],
        target_price=29.99,
        risk_preference="balanced",
    )

    assert state["completed_steps"] == [
        "product_research",
        "profit_analysis",
        "supplier_evaluation",
        "localization",
        "listing_validation",
        "risk_review",
        "await_approval",
    ]
    assert state["evidence"][0]["source"] == "mock_market_trends"
    assert "storage" in state["evidence"][0]["summary"].lower()


def test_product_launch_graph_records_profit_and_listing_validations():
    state = run_product_launch_preview(
        workflow_id="wf_test",
        tenant_id="tenant-a",
        product_idea="foldable under-bed storage organizer",
        target_marketplaces=[
            Marketplace.AMAZON,
            Marketplace.SHOPIFY,
            Marketplace.TIKTOK_SHOP,
        ],
        target_price=29.99,
        risk_preference="balanced",
    )

    assert state["profit_estimate"]["landed_cost"] == 12.8
    assert len(state["listing_validations"]) == 3
    assert {item["marketplace"] for item in state["listing_validations"]} == {
        "amazon",
        "shopify",
        "tiktok_shop",
    }
    assert all(item["valid"] is True for item in state["listing_validations"])


def test_product_launch_graph_records_supplier_evaluation():
    state = run_product_launch_preview(
        workflow_id="wf_supplier",
        tenant_id="tenant-a",
        product_idea="foldable under-bed storage organizer",
        target_marketplaces=[Marketplace.AMAZON],
        target_price=29.99,
        risk_preference="balanced",
    )

    assert state["completed_steps"].index("supplier_evaluation") > state["completed_steps"].index(
        "profit_analysis"
    )
    assert state["completed_steps"].index("supplier_evaluation") < state["completed_steps"].index(
        "listing_validation"
    )
    assert state["selected_supplier_id"] == "SUP-1"
    assert state["supplier_risk_level"] == "low"
    assert len(state["supplier_evaluations"]) >= 2
    assert any(call["tool"] == "score_supplier" for call in state["tool_calls"])


def test_product_launch_graph_records_localization_before_validation():
    state = run_product_launch_preview(
        workflow_id="wf_localization",
        tenant_id="tenant-a",
        product_idea="foldable under-bed storage organizer",
        target_marketplaces=[Marketplace.AMAZON, Marketplace.SHOPIFY],
        target_price=29.99,
        risk_preference="balanced",
        target_locale="en-GB",
    )

    assert state["completed_steps"].index("localization") > state["completed_steps"].index(
        "supplier_evaluation"
    )
    assert state["completed_steps"].index("localization") < state["completed_steps"].index(
        "listing_validation"
    )
    assert len(state["listing_drafts"]) == 2
    assert len(state["localized_listings"]) == 2
    assert all(item["locale"] == "en-GB" for item in state["localized_listings"])
    assert any(call["tool"] == "localize_listing" for call in state["tool_calls"])


def test_product_launch_risk_review_flags_high_supplier_risk():
    state = run_product_launch_preview(
        workflow_id="wf_supplier_risk",
        tenant_id="tenant-a",
        product_idea="foldable under-bed storage organizer",
        target_marketplaces=[Marketplace.AMAZON],
        target_price=29.99,
        risk_preference="supplier_risk",
    )

    assert state["supplier_risk_level"] == "high"
    assert state["selected_supplier_id"] is None
    assert "supplier_risk" in state["approval_reasons"]


def test_product_launch_risk_review_flags_localization_risk():
    state = run_product_launch_preview(
        workflow_id="wf_localization_risk",
        tenant_id="tenant-a",
        product_idea="foldable under-bed storage organizer",
        target_marketplaces=[Marketplace.AMAZON],
        target_price=29.99,
        risk_preference="localization_risk",
        target_locale="en-GB",
    )

    assert state["risk_level"] == RiskLevel.HIGH
    assert state["localization_risk_flags"][0]["risk_level"] == RiskLevel.HIGH.value
    assert state["listing_validations"][0]["valid"] is False
    assert state["listing_validations"][0]["issues"][0]["field"] == "claims"
    assert "localization_risk" in state["approval_reasons"]


def test_product_launch_graph_creates_retrievable_approval_request():
    repo = get_approval_repository()
    repo.clear()

    state = run_product_launch_preview(
        workflow_id="wf_test",
        tenant_id="tenant-a",
        product_idea="foldable under-bed storage organizer",
        target_marketplaces=[Marketplace.AMAZON],
        target_price=29.99,
        risk_preference="balanced",
    )

    approval_id = state["approval_request_id"]
    request = repo.get(approval_id)

    assert request is not None
    assert request.workflow_id == "wf_test"
    assert request.tenant_id == "tenant-a"
    assert request.reason_codes == ["publish_listing"]
    assert state["approval_request"]["status"] == "pending"


def test_product_launch_preview_saves_awaiting_approval_snapshot():
    get_approval_repository().clear()
    snapshots = get_workflow_snapshot_repository()
    snapshots.clear()

    state = run_product_launch_preview(
        workflow_id="wf_snapshot",
        tenant_id="tenant-a",
        product_idea="foldable under-bed storage organizer",
        target_marketplaces=[Marketplace.AMAZON],
        target_price=29.99,
        risk_preference="balanced",
    )
    snapshot = snapshots.get_latest("wf_snapshot", tenant_id="tenant-a")

    assert snapshot is not None
    assert snapshot.checkpoint_name == "await_approval"
    assert snapshot.state["approval_request_id"] == state["approval_request_id"]
    assert snapshot.state["completed_steps"][-1] == "await_approval"


def test_product_launch_preview_records_trace_events():
    get_approval_repository().clear()
    get_workflow_snapshot_repository().clear()
    events = get_trace_event_repository()
    events.clear()

    state = run_product_launch_preview(
        workflow_id="wf_events",
        tenant_id="tenant-a",
        product_idea="foldable under-bed storage organizer",
        target_marketplaces=[Marketplace.AMAZON],
        target_price=29.99,
        risk_preference="balanced",
    )
    workflow_events = events.list_by_workflow(state["workflow_id"], tenant_id="tenant-a")
    names = [event.name for event in workflow_events]

    assert "product_research" in names
    assert "risk_review" in names
    assert "supplier_evaluation" in names
    assert "localization" in names
    assert "approval_requested" in names
    assert "snapshot_saved" in names
    product_research_event = next(event for event in workflow_events if event.name == "product_research")
    assert product_research_event.agent_role == AgentRole.PRODUCT_RESEARCH
    supplier_event = next(event for event in workflow_events if event.name == "supplier_evaluation")
    assert supplier_event.agent_role == AgentRole.SUPPLIER
    localization_event = next(event for event in workflow_events if event.name == "localization")
    assert localization_event.agent_role == AgentRole.LOCALIZATION
    assert localization_event.metadata["target_locale"] == "en-US"
    assert localization_event.metadata["localized_listing_count"] == 1
    assert localization_event.metadata["localization_risk_count"] == 0
    localize_tool_event = next(
        event
        for event in workflow_events
        if event.name == "localize_listing" and event.event_type == TraceEventType.TOOL_CALL
    )
    assert localize_tool_event.agent_role == AgentRole.LOCALIZATION


def test_product_launch_publish_resume_requires_approved_request():
    repo = get_approval_repository()
    repo.clear()
    state = run_product_launch_preview(
        workflow_id="wf_test",
        tenant_id="tenant-a",
        product_idea="foldable under-bed storage organizer",
        target_marketplaces=[Marketplace.AMAZON],
        target_price=29.99,
        risk_preference="balanced",
    )

    resumed = run_product_launch_publish_resume(state["approval_request_id"])

    assert resumed["current_step"] == WorkflowState.FAILED
    assert "approval is not approved" in resumed["errors"]
    assert resumed["publish_results"] == []


def test_product_launch_publish_resume_publishes_all_marketplaces_after_approval():
    repo = get_approval_repository()
    repo.clear()
    state = run_product_launch_preview(
        workflow_id="wf_test",
        tenant_id="tenant-a",
        product_idea="foldable under-bed storage organizer",
        target_marketplaces=[Marketplace.AMAZON, Marketplace.SHOPIFY],
        target_price=29.99,
        risk_preference="balanced",
    )
    repo.approve(state["approval_request_id"], reviewer_id="ops-lead")

    first = run_product_launch_publish_resume(state["approval_request_id"])
    second = run_product_launch_publish_resume(state["approval_request_id"])

    assert first["current_step"] == WorkflowState.COMPLETED
    assert len(first["publish_results"]) == 2
    assert {item["marketplace"] for item in first["publish_results"]} == {"amazon", "shopify"}
    assert first["publish_results"] == second["publish_results"]
    assert all(item["status"] == "published" for item in first["publish_results"])


def test_product_launch_publish_resume_uses_snapshot_not_approval_metadata():
    repo = get_approval_repository()
    repo.clear()
    snapshots = get_workflow_snapshot_repository()
    snapshots.clear()
    state = run_product_launch_preview(
        workflow_id="wf_snapshot",
        tenant_id="tenant-a",
        product_idea="foldable under-bed storage organizer",
        target_marketplaces=[Marketplace.AMAZON],
        target_price=29.99,
        risk_preference="balanced",
    )
    approval = repo.approve(state["approval_request_id"], reviewer_id="ops-lead")
    approval.metadata["target_price"] = 0
    approval.metadata["target_marketplaces"] = []
    repo.replace(approval)

    resumed = run_product_launch_publish_resume(state["approval_request_id"])

    assert resumed["current_step"] == WorkflowState.COMPLETED
    assert len(resumed["publish_results"]) == 1
    assert resumed["target_price"] == 29.99
    assert resumed["localized_listings"][0]["locale"] == "en-US"


def test_product_launch_publish_resume_returns_failed_when_localized_listing_is_invalid():
    repo = get_approval_repository()
    repo.clear()
    get_workflow_snapshot_repository().clear()
    state = run_product_launch_preview(
        workflow_id="wf_invalid_localized_publish",
        tenant_id="tenant-a",
        product_idea="foldable under-bed storage organizer",
        target_marketplaces=[Marketplace.AMAZON],
        target_price=29.99,
        risk_preference="localization_risk",
        target_locale="en-GB",
    )
    repo.approve(state["approval_request_id"], reviewer_id="ops-lead")

    resumed = run_product_launch_publish_resume(state["approval_request_id"])

    assert resumed["current_step"] == WorkflowState.FAILED
    assert resumed["publish_results"] == []
    assert "Cannot publish invalid listing: claims" in resumed["errors"]


def test_product_launch_publish_resume_records_publish_tool_events():
    repo = get_approval_repository()
    repo.clear()
    get_workflow_snapshot_repository().clear()
    events = get_trace_event_repository()
    events.clear()
    state = run_product_launch_preview(
        workflow_id="wf_publish_events",
        tenant_id="tenant-a",
        product_idea="foldable under-bed storage organizer",
        target_marketplaces=[Marketplace.AMAZON, Marketplace.SHOPIFY],
        target_price=29.99,
        risk_preference="balanced",
    )
    repo.approve(state["approval_request_id"], reviewer_id="ops-lead")

    resumed = run_product_launch_publish_resume(state["approval_request_id"])

    workflow_events = events.list_by_workflow(state["workflow_id"], tenant_id="tenant-a")
    publish_events = [
        event
        for event in workflow_events
        if event.name == "publish_listing" and event.event_type == TraceEventType.TOOL_CALL
    ]

    assert resumed["current_step"] == WorkflowState.COMPLETED
    assert len(publish_events) == len(resumed["publish_results"])
    assert all(event.event_type == TraceEventType.TOOL_CALL for event in publish_events)
