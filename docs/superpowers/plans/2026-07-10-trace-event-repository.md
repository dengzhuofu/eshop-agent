# Trace Event Repository Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist workflow trace/audit events and expose them through a workflow events API.

**Architecture:** Reuse the existing `TraceEvent` schema and add an in-memory repository with tenant isolation and secret metadata protection. The product-launch workflow records coarse-grained but useful events after preview and publish resume: completed graph steps, approval request, snapshot save, publish tool calls, and failure reasons. FastAPI exposes `GET /workflows/{workflow_id}/events` for future UI/debug panels.

**Tech Stack:** Python, FastAPI, Pydantic, pytest, LangGraph.

## Global Constraints

- Do not call real marketplace APIs.
- Events must include workflow ID, tenant ID, agent role, event type, name, metadata, and created timestamp.
- Event reads must enforce tenant matching.
- Event metadata must reject secret-like keys.
- Route functions remain pure; event writes happen in workflow orchestration, not graph route functions.
- Event recording should not change business state semantics.
- Add a Node 12 progress log under `docs/progress/`.

---

## File Structure

- Modify `backend/app/agents/observability/schema.py`: add `CHECKPOINT` trace type.
- Create `backend/app/repositories/events.py`: in-memory trace event repository.
- Modify `backend/app/agents/graphs/workflows/product_launch.py`: record preview/resume events.
- Modify `backend/app/api/routes/workflows.py`: add `GET /workflows/{workflow_id}/events`.
- Create `backend/tests/test_trace_events.py`: repository tests.
- Modify `backend/tests/test_product_launch_graph.py`: workflow event tests.
- Modify `backend/tests/test_workflows_api.py`: events API tests.
- Add `docs/progress/2026-07-10-node-12-trace-event-repository.md`: Node 12 summary log.

## Tasks

### Task 1: Trace event repository

**Files:**
- Create: `backend/app/repositories/events.py`
- Modify: `backend/app/agents/observability/schema.py`
- Test: `backend/tests/test_trace_events.py`

**Interfaces:**
- Consumes: `TraceEvent`, `TraceEventType`, `create_trace_event`
- Produces:
  - `TraceEventRepository`
  - `TraceEventConflictError`
  - `TraceEventSecurityError`
  - `get_trace_event_repository`

- [ ] **Step 1: Write failing repository tests**

```python
from app.agents.observability.schema import TraceEventType, create_trace_event
from app.domain.enums import AgentRole
from app.repositories.events import (
    TraceEventConflictError,
    TraceEventRepository,
    TraceEventSecurityError,
)


def test_trace_event_repository_records_events_in_order():
    repo = TraceEventRepository()
    first = create_trace_event("wf_test", "tenant-a", AgentRole.SUPERVISOR, TraceEventType.NODE_END, "risk_review")
    second = create_trace_event("wf_test", "tenant-a", AgentRole.SUPERVISOR, TraceEventType.CHECKPOINT, "snapshot_saved")

    repo.record(first)
    repo.record(second)

    events = repo.list_by_workflow("wf_test", tenant_id="tenant-a")
    assert [event.name for event in events] == ["risk_review", "snapshot_saved"]


def test_trace_event_repository_enforces_tenant_isolation():
    repo = TraceEventRepository()
    repo.record(create_trace_event("wf_test", "tenant-a", AgentRole.SUPERVISOR, TraceEventType.NODE_END, "risk_review"))

    try:
        repo.list_by_workflow("wf_test", tenant_id="tenant-b")
    except TraceEventConflictError as exc:
        assert "tenant mismatch" in str(exc)
    else:
        raise AssertionError("Expected tenant mismatch to be rejected")


def test_trace_event_repository_rejects_secret_like_metadata():
    repo = TraceEventRepository()
    event = create_trace_event(
        "wf_test",
        "tenant-a",
        AgentRole.SUPERVISOR,
        TraceEventType.NODE_END,
        "risk_review",
        metadata={"api_key": "sk-real-secret"},
    )

    try:
        repo.record(event)
    except TraceEventSecurityError as exc:
        assert "secret-like event metadata key: api_key" in str(exc)
    else:
        raise AssertionError("Expected secret-like event metadata to be rejected")
```

- [ ] **Step 2: Run repository tests to verify they fail**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_trace_events.py -v
```

Expected: FAIL because `app.repositories.events` and `TraceEventType.CHECKPOINT` do not exist.

- [ ] **Step 3: Implement repository and trace type**

Add `TraceEventType.CHECKPOINT = "checkpoint"`.

Implement:
- `record(event: TraceEvent) -> TraceEvent`
- `list_by_workflow(workflow_id: str, tenant_id: str) -> list[TraceEvent]`
- `clear() -> None`

Rules:
- Preserve insertion order.
- Return deep copies.
- Reject tenant mismatch reads.
- Reject secret-like metadata keys recursively.

- [ ] **Step 4: Run repository tests to verify they pass**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_trace_events.py -v
```

Expected: PASS.

### Task 2: Workflow trace events

**Files:**
- Modify: `backend/app/agents/graphs/workflows/product_launch.py`
- Modify: `backend/tests/test_product_launch_graph.py`

**Interfaces:**
- Consumes: `get_trace_event_repository().record(...)`
- Produces: preview and resume events

- [ ] **Step 1: Write failing workflow event tests**

Add:

```python
from app.repositories.events import get_trace_event_repository


def test_product_launch_preview_records_trace_events():
    get_approval_repository().clear()
    get_workflow_snapshot_repository().clear()
    events = get_trace_event_repository()
    events.clear()

    state = run_product_launch_preview(...)
    workflow_events = events.list_by_workflow(state["workflow_id"], tenant_id="tenant-a")
    names = [event.name for event in workflow_events]

    assert "product_research" in names
    assert "risk_review" in names
    assert "approval_requested" in names
    assert "snapshot_saved" in names


def test_product_launch_publish_resume_records_publish_tool_events():
    get_approval_repository().clear()
    get_workflow_snapshot_repository().clear()
    events = get_trace_event_repository()
    events.clear()

    state = run_product_launch_preview(...)
    get_approval_repository().approve(state["approval_request_id"], reviewer_id="ops-lead")
    resumed = run_product_launch_publish_resume(state["approval_request_id"])

    workflow_events = events.list_by_workflow(state["workflow_id"], tenant_id="tenant-a")
    publish_events = [event for event in workflow_events if event.name == "publish_listing"]

    assert resumed["current_step"] == WorkflowState.COMPLETED
    assert len(publish_events) == len(resumed["publish_results"])
    assert all(event.event_type == TraceEventType.TOOL_CALL for event in publish_events)
```

- [ ] **Step 2: Run graph tests to verify they fail**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_product_launch_graph.py::test_product_launch_preview_records_trace_events tests/test_product_launch_graph.py::test_product_launch_publish_resume_records_publish_tool_events -v
```

Expected: FAIL because workflows do not record events yet.

- [ ] **Step 3: Implement workflow event recording**

Add helper functions in `product_launch.py` workflow module:
- `_record_completed_step_events(state)`
- `_record_tool_call_events(state, only_tool: str | None = None)`
- `_record_approval_and_checkpoint_events(state, snapshot)`
- `_record_error_events(state)`

Preview recording:
- `NODE_END` for each completed step.
- `TOOL_CALL` for each tool call in state.
- `APPROVAL` event named `approval_requested`.
- `CHECKPOINT` event named `snapshot_saved`.

Resume recording:
- `NODE_END` for `publish_listing`.
- `TOOL_CALL` for each publish listing call.
- `ERROR` event for failed resume.

- [ ] **Step 4: Run graph tests to verify they pass**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_product_launch_graph.py -v
```

Expected: PASS.

### Task 3: Events API

**Files:**
- Modify: `backend/app/api/routes/workflows.py`
- Modify: `backend/tests/test_workflows_api.py`

**Interfaces:**
- Produces: `GET /workflows/{workflow_id}/events`

- [ ] **Step 1: Write failing API test**

Add:

```python
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
```

- [ ] **Step 2: Run API test to verify it fails**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_workflows_api.py::test_workflow_events_endpoint_returns_trace_events -v
```

Expected: FAIL because events endpoint does not exist.

- [ ] **Step 3: Implement API endpoint**

Add `GET /workflows/{workflow_id}/events`.

MVP uses `tenant_id="demo-tenant"`.

Return:

```python
{"workflow_id": workflow_id, "events": [event.model_dump(mode="json") for event in events]}
```

Return 409 on tenant mismatch.

- [ ] **Step 4: Run API tests to verify they pass**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_workflows_api.py -v
```

Expected: PASS.

### Task 4: Verification, progress log, push

**Files:**
- Add: `docs/progress/2026-07-10-node-12-trace-event-repository.md`

- [ ] **Step 1: Run focused tests**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_trace_events.py tests/test_product_launch_graph.py tests/test_workflows_api.py -v
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
- trace repository behavior
- tenant isolation and secret metadata rule
- preview/resume recorded events
- API endpoint
- verification result
- next node recommendation

- [ ] **Step 4: Commit and push**

```powershell
git add backend docs
git commit -m "feat: add workflow trace events"
git push -u origin codex/node-12-trace-events
```
