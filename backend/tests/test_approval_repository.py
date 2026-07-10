from app.domain.enums import ApprovalStatus, RiskLevel
from app.repositories.approvals import ApprovalConflictError, ApprovalRepository


def test_upsert_pending_request_is_idempotent():
    repo = ApprovalRepository()

    first = repo.upsert_pending(
        approval_id="appr_wf_test",
        workflow_id="wf_test",
        tenant_id="tenant-a",
        requested_by="supervisor",
        reason_codes=["publish_listing"],
        risk_level=RiskLevel.HIGH,
        resource_type="workflow",
        resource_id="wf_test",
        metadata={"tool": "publish_listing"},
    )
    second = repo.upsert_pending(
        approval_id="appr_wf_test",
        workflow_id="wf_test",
        tenant_id="tenant-a",
        requested_by="supervisor",
        reason_codes=["publish_listing"],
        risk_level=RiskLevel.HIGH,
        resource_type="workflow",
        resource_id="wf_test",
        metadata={"tool": "publish_listing"},
    )

    assert first.id == second.id
    assert second.status == ApprovalStatus.PENDING
    assert len(repo.list()) == 1


def test_approve_and_reject_transitions_are_guarded():
    repo = ApprovalRepository()
    repo.upsert_pending(
        approval_id="appr_wf_test",
        workflow_id="wf_test",
        tenant_id="tenant-a",
        requested_by="supervisor",
        reason_codes=["publish_listing"],
        risk_level=RiskLevel.HIGH,
        resource_type="workflow",
        resource_id="wf_test",
        metadata={},
    )

    approved = repo.approve("appr_wf_test", reviewer_id="ops-lead", comment="ok")

    assert approved.status == ApprovalStatus.APPROVED
    assert approved.reviewed_by == "ops-lead"

    same = repo.approve("appr_wf_test", reviewer_id="ops-lead", comment="ok")
    assert same.status == ApprovalStatus.APPROVED

    try:
        repo.reject("appr_wf_test", reviewer_id="ops-lead", comment="too late")
    except ApprovalConflictError as exc:
        assert "already approved" in str(exc)
    else:
        raise AssertionError("Expected approved request to reject cross-terminal transition")
