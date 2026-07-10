# Workflow Snapshot Repository Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist workflow state snapshots at approval checkpoints and use those snapshots to resume approved publishing.

**Architecture:** Add an in-memory workflow snapshot repository as a persistence boundary. The product-launch preview runner saves a snapshot after the LangGraph preview reaches `await_approval`. The publish resume runner loads the snapshot by workflow and tenant, overlays the latest approval request, and resumes publishing from the stored state instead of rebuilding business state from approval metadata. This is a business snapshot layer for MVP, not a replacement for LangGraph's future checkpointer.

**Tech Stack:** Python, FastAPI, Pydantic, pytest, LangGraph.

## Global Constraints

- Do not call real marketplace APIs.
- Do not store raw secrets in snapshots.
- Snapshot reads must enforce tenant matching.
- Resume must use stored workflow state, not approval metadata, for product idea, target marketplaces, price, evidence, validations, and tool history.
- Approval metadata may retain compatibility fields, but it must not be the resume source of truth.
- Snapshot creation must be idempotent per workflow ID and checkpoint name.
- Route functions remain pure; snapshot writes happen in workflow orchestration, not graph route functions.
- Add a Node 11 progress log under `docs/progress/`.

---

## File Structure

- Create `backend/app/domain/snapshots.py`: snapshot models.
- Create `backend/app/repositories/snapshots.py`: in-memory snapshot repository.
- Modify `backend/app/agents/graphs/workflows/product_launch.py`: save preview snapshot and load it during publish resume.
- Modify `backend/app/api/routes/workflows.py`: include snapshot metadata in create/resume responses where useful.
- Create `backend/tests/test_workflow_snapshots.py`: repository and tenant isolation tests.
- Modify `backend/tests/test_product_launch_graph.py`: verify resume loads snapshot state rather than approval metadata.
- Modify `backend/tests/test_workflows_api.py`: verify API conflict for missing snapshot and snapshot-backed resume success.
- Add `docs/progress/2026-07-10-node-11-workflow-snapshot-repository.md`: Node 11 summary log.

## Tasks

### Task 1: Snapshot repository

**Files:**
- Create: `backend/app/domain/snapshots.py`
- Create: `backend/app/repositories/snapshots.py`
- Test: `backend/tests/test_workflow_snapshots.py`

**Interfaces:**
- Produces:
  - `WorkflowSnapshot`
  - `WorkflowSnapshotConflictError`
  - `WorkflowSnapshotRepository`
  - `get_workflow_snapshot_repository`

- [ ] **Step 1: Write failing repository tests**

```python
from app.domain.enums import AgentRole, WorkflowState
from app.repositories.snapshots import (
    WorkflowSnapshotConflictError,
    WorkflowSnapshotRepository,
)


def test_workflow_snapshot_repository_saves_latest_checkpoint_snapshot():
    repo = WorkflowSnapshotRepository()
    first = repo.save(
        workflow_id="wf_test",
        tenant_id="tenant-a",
        checkpoint_name="await_approval",
        state={
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
        },
    )
    second = repo.save(
        workflow_id="wf_test",
        tenant_id="tenant-a",
        checkpoint_name="await_approval",
        state={**first.state, "target_price": 31.99},
    )

    loaded = repo.get_latest("wf_test", tenant_id="tenant-a")

    assert loaded is not None
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
```

- [ ] **Step 2: Run repository tests to verify they fail**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_workflow_snapshots.py -v
```

Expected: FAIL because `app.repositories.snapshots` does not exist.

- [ ] **Step 3: Implement minimal repository**

Create `WorkflowSnapshot` with fields:
- `id: str`
- `workflow_id: str`
- `tenant_id: str`
- `checkpoint_name: str`
- `version: int`
- `state: dict[str, Any]`
- `created_at: datetime`

Implement:
- `save(workflow_id, tenant_id, checkpoint_name, state) -> WorkflowSnapshot`
- `get_latest(workflow_id, tenant_id) -> WorkflowSnapshot | None`
- `clear() -> None`

Rules:
- Version increments for same workflow ID.
- Returned objects are deep copies.
- If workflow exists but requested tenant differs, raise `WorkflowSnapshotConflictError("tenant mismatch")`.

- [ ] **Step 4: Run repository tests to verify they pass**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_workflow_snapshots.py -v
```

Expected: PASS.

### Task 2: Preview snapshot integration

**Files:**
- Modify: `backend/app/agents/graphs/workflows/product_launch.py`
- Modify: `backend/tests/test_product_launch_graph.py`

**Interfaces:**
- Consumes: `get_workflow_snapshot_repository().save(...)`
- Produces: snapshot saved after `run_product_launch_preview(...)`

- [ ] **Step 1: Write failing graph test**

Add:

```python
from app.repositories.snapshots import get_workflow_snapshot_repository


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
```

- [ ] **Step 2: Run graph test to verify it fails**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_product_launch_graph.py::test_product_launch_preview_saves_awaiting_approval_snapshot -v
```

Expected: FAIL because preview runner does not save snapshots yet.

- [ ] **Step 3: Save snapshot after preview graph execution**

In `run_product_launch_preview`, after graph invocation:
- if final state is `WorkflowState.AWAITING_APPROVAL`, save checkpoint `await_approval`.
- return state unchanged except optional `snapshot_id` is not required in state.

- [ ] **Step 4: Run graph tests to verify they pass**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_product_launch_graph.py -v
```

Expected: PASS.

### Task 3: Snapshot-backed resume

**Files:**
- Modify: `backend/app/agents/graphs/workflows/product_launch.py`
- Modify: `backend/tests/test_product_launch_graph.py`

**Interfaces:**
- Consumes: latest snapshot for approval workflow and tenant
- Produces: `run_product_launch_publish_resume` uses snapshot state as source of truth

- [ ] **Step 1: Write failing resume test**

Add:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_product_launch_graph.py::test_product_launch_publish_resume_uses_snapshot_not_approval_metadata -v
```

Expected: FAIL because resume still rebuilds state from approval metadata.

- [ ] **Step 3: Add repository replace and snapshot-backed resume**

Add `ApprovalRepository.replace(request)` for testable mutation of approval records.

Update `run_product_launch_publish_resume`:
- load approval
- load latest snapshot with `approval.workflow_id` and `approval.tenant_id`
- if no snapshot, return failed state with error `workflow snapshot not found`
- copy snapshot state as initial state
- overlay latest approval fields:
  - `approval_request_id`
  - `approval_request`
  - `approval_reasons`
  - `risk_level`
- invoke publish graph

- [ ] **Step 4: Run graph tests to verify they pass**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_product_launch_graph.py -v
```

Expected: PASS.

### Task 4: API response and missing snapshot behavior

**Files:**
- Modify: `backend/app/api/routes/workflows.py`
- Modify: `backend/tests/test_workflows_api.py`

**Interfaces:**
- Produces API evidence that preview saved snapshot and resume fails clearly without snapshot

- [ ] **Step 1: Write failing API tests**

Add:

```python
def test_create_workflow_response_includes_snapshot_metadata():
    get_approval_repository().clear()
    get_workflow_snapshot_repository().clear()
    client = TestClient(create_app())

    response = client.post("/workflows", json=WORKFLOW_REQUEST)
    data = response.json()

    assert data["snapshot"]["checkpoint_name"] == "await_approval"
    assert data["snapshot"]["version"] == 1


def test_workflow_resume_returns_409_when_snapshot_is_missing():
    get_approval_repository().clear()
    get_workflow_snapshot_repository().clear()
    client = TestClient(create_app())
    response = client.post("/workflows", json=WORKFLOW_REQUEST)
    approval_id = response.json()["approval_request_id"]
    workflow_id = response.json()["workflow_id"]
    client.post(f"/approvals/{approval_id}/approve", json={"reviewer_id": "ops-lead"})
    get_workflow_snapshot_repository().clear()

    resumed = client.post(f"/workflows/{workflow_id}/resume", json={"approval_request_id": approval_id})

    assert resumed.status_code == 409
    assert "workflow snapshot not found" in resumed.json()["detail"]
```

- [ ] **Step 2: Run API tests to verify they fail**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_workflows_api.py -v
```

Expected: FAIL because workflow response does not expose snapshot metadata and resume does not use snapshot yet.

- [ ] **Step 3: Implement API snapshot metadata**

In `create_workflow`, load latest snapshot after preview and return:

```python
"snapshot": {
    "id": snapshot.id,
    "checkpoint_name": snapshot.checkpoint_name,
    "version": snapshot.version,
}
```

When resume returns failed state, keep existing 409 mapping so missing snapshot is surfaced.

- [ ] **Step 4: Run API tests to verify they pass**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_workflows_api.py -v
```

Expected: PASS.

### Task 5: Verification, progress log, push

**Files:**
- Add: `docs/progress/2026-07-10-node-11-workflow-snapshot-repository.md`

- [ ] **Step 1: Run focused tests**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_workflow_snapshots.py tests/test_product_launch_graph.py tests/test_workflows_api.py -v
```

Expected: PASS.

- [ ] **Step 2: Run full tests**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -v
```

Expected: PASS.

- [ ] **Step 3: Add progress log**

Document:
- snapshot repository behavior
- preview checkpoint save behavior
- snapshot-backed resume behavior
- tenant isolation rule
- verification result
- next node recommendation

- [ ] **Step 4: Commit and push**

```powershell
git add backend docs
git commit -m "feat: add workflow snapshot repository"
git push -u origin codex/node-11-workflow-snapshots
```
