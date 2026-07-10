from fastapi.testclient import TestClient

from app.domain.enums import RiskLevel
from app.main import create_app
from app.repositories.approvals import get_approval_repository


def _seed_pending_approval() -> str:
    approval_id = "appr_wf_test"
    get_approval_repository().upsert_pending(
        approval_id=approval_id,
        workflow_id="wf_test",
        tenant_id="tenant-a",
        requested_by="supervisor",
        reason_codes=["publish_listing"],
        risk_level=RiskLevel.HIGH,
        resource_type="workflow",
        resource_id="wf_test",
        metadata={"tool": "publish_listing"},
    )
    return approval_id


def test_approval_api_lists_gets_and_approves_request():
    repo = get_approval_repository()
    repo.clear()
    approval_id = _seed_pending_approval()
    client = TestClient(create_app())

    listing = client.get("/approvals")
    detail = client.get(f"/approvals/{approval_id}")
    approved = client.post(
        f"/approvals/{approval_id}/approve",
        json={"reviewer_id": "ops-lead", "comment": "approved for mock publish"},
    )

    assert listing.status_code == 200
    assert len(listing.json()["approvals"]) == 1
    assert detail.json()["id"] == approval_id
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"


def test_approval_api_returns_404_and_409_for_invalid_transitions():
    repo = get_approval_repository()
    repo.clear()
    approval_id = _seed_pending_approval()
    client = TestClient(create_app())

    missing = client.get("/approvals/appr_missing")
    assert missing.status_code == 404

    client.post(f"/approvals/{approval_id}/reject", json={"reviewer_id": "ops-lead"})

    conflict = client.post(f"/approvals/{approval_id}/approve", json={"reviewer_id": "ops-lead"})
    assert conflict.status_code == 409
