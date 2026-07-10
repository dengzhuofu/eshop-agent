from app.domain.enums import AgentRole, WorkflowState
from app.repositories.snapshots import (
    WorkflowSnapshotConflictError,
    WorkflowSnapshotRepository,
    WorkflowSnapshotSecurityError,
)


def test_workflow_snapshot_repository_saves_latest_checkpoint_snapshot():
    repo = WorkflowSnapshotRepository()
    initial_state = {
        "workflow_id": "wf_test",
        "tenant_id": "tenant-a",
        "current_agent": AgentRole.SUPERVISOR,
        "current_step": WorkflowState.AWAITING_APPROVAL,
        "product_idea": "foldable organizer",
        "target_marketplaces": ["amazon"],
        "target_price": 29.99,
        "messages": [],
        "tool_calls": [],
        "approval_request_id": "appr_wf_test",
    }
    first = repo.save(
        workflow_id="wf_test",
        tenant_id="tenant-a",
        checkpoint_name="await_approval",
        state=initial_state,
    )
    repeated = repo.save(
        workflow_id="wf_test",
        tenant_id="tenant-a",
        checkpoint_name="await_approval",
        state=initial_state,
    )
    second = repo.save(
        workflow_id="wf_test",
        tenant_id="tenant-a",
        checkpoint_name="await_approval",
        state={**first.state, "target_price": 31.99},
    )

    loaded = repo.get_latest("wf_test", tenant_id="tenant-a")

    assert loaded is not None
    assert repeated.id == first.id
    assert repeated.version == 1
    assert loaded.id == second.id
    assert loaded.version == 2
    assert loaded.state["target_price"] == 31.99


def test_workflow_snapshot_repository_enforces_tenant_isolation():
    repo = WorkflowSnapshotRepository()
    repo.save(
        workflow_id="wf_test",
        tenant_id="tenant-a",
        checkpoint_name="await_approval",
        state={"workflow_id": "wf_test", "tenant_id": "tenant-a"},
    )

    try:
        repo.get_latest("wf_test", tenant_id="tenant-b")
    except WorkflowSnapshotConflictError as exc:
        assert "tenant mismatch" in str(exc)
    else:
        raise AssertionError("Expected tenant mismatch to be rejected")


def test_workflow_snapshot_repository_rejects_secret_like_state():
    repo = WorkflowSnapshotRepository()

    try:
        repo.save(
            workflow_id="wf_test",
            tenant_id="tenant-a",
            checkpoint_name="await_approval",
            state={"workflow_id": "wf_test", "tenant_id": "tenant-a", "api_key": "sk-real-secret"},
        )
    except WorkflowSnapshotSecurityError as exc:
        assert "secret-like snapshot key: api_key" in str(exc)
    else:
        raise AssertionError("Expected secret-like snapshot state to be rejected")


def test_workflow_snapshot_repository_is_immutable_from_caller_mutation():
    repo = WorkflowSnapshotRepository()
    state = {
        "workflow_id": "wf_test",
        "tenant_id": "tenant-a",
        "target_price": 29.99,
        "messages": [],
    }

    repo.save(
        workflow_id="wf_test",
        tenant_id="tenant-a",
        checkpoint_name="await_approval",
        state=state,
    )
    state["target_price"] = 0
    state["messages"].append({"content": "mutated outside repository"})

    loaded = repo.get_latest("wf_test", tenant_id="tenant-a")

    assert loaded is not None
    assert loaded.state["target_price"] == 29.99
    assert loaded.state["messages"] == []
