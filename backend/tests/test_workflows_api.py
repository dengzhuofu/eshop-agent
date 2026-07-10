from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.approvals import get_approval_repository
from app.repositories.events import get_trace_event_repository
from app.repositories.snapshots import get_workflow_snapshot_repository


WORKFLOW_REQUEST = {
    "product_idea": "foldable under-bed storage organizer",
    "target_marketplaces": ["amazon", "shopify", "tiktok_shop"],
    "target_price": 29.99,
    "risk_preference": "balanced",
}


def test_marketplace_rules_endpoint_returns_amazon_constraints():
    client = TestClient(create_app())

    response = client.get("/marketplaces/amazon/rules")

    assert response.status_code == 200
    data = response.json()
    assert data["marketplace"] == "amazon"
    assert data["max_title_length"] == 200
    assert data["required_bullet_points"] == 3


def test_create_workflow_returns_deterministic_preview():
    get_approval_repository().clear()
    get_workflow_snapshot_repository().clear()
    client = TestClient(create_app())

    response = client.post(
        "/workflows",
        json=WORKFLOW_REQUEST,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["workflow_id"].startswith("wf_")
    assert data["state"] == "awaiting_approval"
    assert data["approval_required"] is True
    assert data["approval_request_id"].startswith("appr_")
    assert data["approval_request"]["status"] == "pending"
    assert data["approval_request"]["workflow_id"] == data["workflow_id"]
    assert data["profit_estimate"]["landed_cost"] == 12.8
    assert len(data["listing_validations"]) == 3
    assert {item["marketplace"] for item in data["listing_validations"]} == {
        "amazon",
        "shopify",
        "tiktok_shop",
    }
    assert "publish_listing" in data["approval_reasons"]


def test_create_workflow_response_includes_snapshot_metadata():
    get_approval_repository().clear()
    get_workflow_snapshot_repository().clear()
    client = TestClient(create_app())

    response = client.post("/workflows", json=WORKFLOW_REQUEST)
    data = response.json()

    assert data["snapshot"]["checkpoint_name"] == "await_approval"
    assert data["snapshot"]["version"] == 1


def test_workflow_resume_publishes_after_approval():
    get_approval_repository().clear()
    get_workflow_snapshot_repository().clear()
    client = TestClient(create_app())
    response = client.post("/workflows", json=WORKFLOW_REQUEST)
    approval_id = response.json()["approval_request_id"]
    workflow_id = response.json()["workflow_id"]
    client.post(f"/approvals/{approval_id}/approve", json={"reviewer_id": "ops-lead"})

    resumed = client.post(f"/workflows/{workflow_id}/resume", json={"approval_request_id": approval_id})

    assert resumed.status_code == 200
    data = resumed.json()
    assert data["state"] == "completed"
    assert data["approval_request_id"] == approval_id
    assert len(data["publish_results"]) == 3
    assert all(item["status"] == "published" for item in data["publish_results"])


def test_workflow_resume_returns_409_when_approval_not_approved():
    get_approval_repository().clear()
    get_workflow_snapshot_repository().clear()
    client = TestClient(create_app())
    response = client.post("/workflows", json=WORKFLOW_REQUEST)
    approval_id = response.json()["approval_request_id"]
    workflow_id = response.json()["workflow_id"]

    resumed = client.post(f"/workflows/{workflow_id}/resume", json={"approval_request_id": approval_id})

    assert resumed.status_code == 409


def test_workflow_resume_returns_409_when_snapshot_is_missing():
    get_approval_repository().clear()
    snapshots = get_workflow_snapshot_repository()
    snapshots.clear()
    client = TestClient(create_app())
    response = client.post("/workflows", json=WORKFLOW_REQUEST)
    approval_id = response.json()["approval_request_id"]
    workflow_id = response.json()["workflow_id"]
    client.post(f"/approvals/{approval_id}/approve", json={"reviewer_id": "ops-lead"})
    snapshots.clear()

    resumed = client.post(f"/workflows/{workflow_id}/resume", json={"approval_request_id": approval_id})

    assert resumed.status_code == 409
    assert "workflow snapshot not found" in resumed.json()["detail"]


def test_workflow_events_endpoint_returns_trace_events():
    get_approval_repository().clear()
    get_workflow_snapshot_repository().clear()
    get_trace_event_repository().clear()
    client = TestClient(create_app())
    response = client.post("/workflows", json=WORKFLOW_REQUEST)
    workflow_id = response.json()["workflow_id"]

    events_response = client.get(f"/workflows/{workflow_id}/events")

    assert events_response.status_code == 200
    names = [event["name"] for event in events_response.json()["events"]]
    assert "approval_requested" in names
    assert "snapshot_saved" in names
