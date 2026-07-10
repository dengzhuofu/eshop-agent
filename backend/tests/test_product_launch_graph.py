from app.agents.graphs.workflows.product_launch import (
    run_product_launch_preview,
    run_product_launch_publish_resume,
)
from app.domain.enums import Marketplace, WorkflowState
from app.repositories.approvals import get_approval_repository


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
