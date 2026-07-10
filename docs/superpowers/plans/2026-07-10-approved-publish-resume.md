# Approved Publish Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resume a product-launch workflow after approval and execute mock marketplace publishing with idempotent results.

**Architecture:** Keep approval review and publishing as separate steps. `await_approval` stores enough launch metadata to rebuild deterministic listing drafts. A new publish node checks that the approval request exists and is approved before calling mock marketplace adapters. A workflow resume API invokes the publish resume path and returns publish results without touching real external platforms.

**Tech Stack:** Python, FastAPI, Pydantic, pytest, LangGraph.

## Global Constraints

- Do not call real marketplace APIs.
- Do not execute publish when approval is pending, rejected, or missing.
- Use stable idempotency keys per approval and marketplace.
- Keep route functions pure; publish execution belongs in a node/workflow function.
- Preserve tenant and workflow IDs in publish results.
- Add a Node 10 progress log under `docs/progress/`.

---

## File Structure

- Modify `backend/app/agents/graphs/state.py`: add `publish_results`.
- Modify `backend/app/agents/graphs/nodes/product_launch.py`: add `publish_listing_node`; include `target_price` in approval metadata.
- Modify `backend/app/agents/graphs/workflows/product_launch.py`: add `run_product_launch_publish_resume`.
- Modify `backend/app/api/routes/workflows.py`: add `POST /workflows/{workflow_id}/resume`.
- Modify `backend/tests/test_product_launch_graph.py`: test approved publish resume.
- Modify `backend/tests/test_workflows_api.py`: test resume endpoint success and conflict.
- Add `docs/progress/2026-07-10-node-10-approved-publish-resume.md`: Node 10 summary log.

## Tasks

### Task 1: Graph resume tests

**Files:**
- Modify: `backend/tests/test_product_launch_graph.py`

**Interfaces:**
- Consumes: `run_product_launch_preview`, `run_product_launch_publish_resume`, `get_approval_repository`
- Produces: tested behavior for approved, pending, and idempotent publish resume

- [ ] **Step 1: Write failing graph tests**

Add tests:

```python
from app.agents.graphs.workflows.product_launch import run_product_launch_publish_resume


def test_product_launch_publish_resume_requires_approved_request():
    repo = get_approval_repository()
    repo.clear()
    state = run_product_launch_preview(...)

    resumed = run_product_launch_publish_resume(state["approval_request_id"])

    assert resumed["current_step"] == WorkflowState.FAILED
    assert "approval is not approved" in resumed["errors"]


def test_product_launch_publish_resume_publishes_all_marketplaces_after_approval():
    repo = get_approval_repository()
    repo.clear()
    state = run_product_launch_preview(...)
    repo.approve(state["approval_request_id"], reviewer_id="ops-lead")

    first = run_product_launch_publish_resume(state["approval_request_id"])
    second = run_product_launch_publish_resume(state["approval_request_id"])

    assert first["current_step"] == WorkflowState.COMPLETED
    assert len(first["publish_results"]) == 2
    assert first["publish_results"] == second["publish_results"]
```

- [ ] **Step 2: Run graph tests to verify they fail**

Run: `python -m pytest tests/test_product_launch_graph.py -v` from `backend/`

Expected: FAIL because `run_product_launch_publish_resume` does not exist.

- [ ] **Step 3: Implement publish resume node and workflow**

Implementation details:
- Add `publish_results: list[dict[str, Any]]` to state.
- Add `target_price` to `await_approval_node` approval metadata.
- Add `publish_listing_node(state)`.
- In `publish_listing_node`, load approval by `approval_request_id`.
- If missing, return `WorkflowState.FAILED` and error `approval request not found`.
- If not approved, return `WorkflowState.FAILED` and error `approval is not approved`.
- For each marketplace in `state["target_marketplaces"]`, call `adapter.publish_listing(...)`.
- Use idempotency key `f"{approval_id}:{marketplace}"`.
- Return `publish_results`, append publish tool calls, set `current_step=WorkflowState.COMPLETED`.
- Add `run_product_launch_publish_resume(approval_request_id)` that rebuilds state from approval metadata and runs a small graph: `START -> publish_listing -> END`.

- [ ] **Step 4: Run graph tests to verify they pass**

Run: `python -m pytest tests/test_product_launch_graph.py -v` from `backend/`

Expected: PASS.

### Task 2: Workflow resume API tests

**Files:**
- Modify: `backend/tests/test_workflows_api.py`
- Modify later: `backend/app/api/routes/workflows.py`

**Interfaces:**
- Produces: `POST /workflows/{workflow_id}/resume`

- [ ] **Step 1: Write failing API tests**

Add tests:

```python
def test_workflow_resume_publishes_after_approval():
    client = TestClient(create_app())
    response = client.post("/workflows", json={...})
    approval_id = response.json()["approval_request_id"]
    workflow_id = response.json()["workflow_id"]
    client.post(f"/approvals/{approval_id}/approve", json={"reviewer_id": "ops-lead"})

    resumed = client.post(f"/workflows/{workflow_id}/resume", json={"approval_request_id": approval_id})

    assert resumed.status_code == 200
    assert resumed.json()["state"] == "completed"
    assert len(resumed.json()["publish_results"]) >= 1


def test_workflow_resume_returns_409_when_approval_not_approved():
    client = TestClient(create_app())
    response = client.post("/workflows", json={...})
    approval_id = response.json()["approval_request_id"]
    workflow_id = response.json()["workflow_id"]

    resumed = client.post(f"/workflows/{workflow_id}/resume", json={"approval_request_id": approval_id})

    assert resumed.status_code == 409
```

- [ ] **Step 2: Run API tests to verify they fail**

Run: `python -m pytest tests/test_workflows_api.py -v` from `backend/`

Expected: FAIL because `/workflows/{workflow_id}/resume` does not exist.

- [ ] **Step 3: Implement resume endpoint**

Add request model:

```python
class WorkflowResumeRequest(BaseModel):
    approval_request_id: str = Field(min_length=1)
```

Endpoint behavior:
- 404 when approval request is missing.
- 409 when approval workflow ID does not match path workflow ID.
- 409 when publish resume returns failed state.
- 200 with workflow ID, state, approval ID, publish results, tool calls, and completed steps on success.

- [ ] **Step 4: Run API tests to verify they pass**

Run: `python -m pytest tests/test_workflows_api.py -v` from `backend/`

Expected: PASS.

### Task 3: Verification and progress log

**Files:**
- Add: `docs/progress/2026-07-10-node-10-approved-publish-resume.md`

- [ ] **Step 1: Run focused tests**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_product_launch_graph.py tests/test_workflows_api.py -v
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
- approved publish resume behavior
- rejection/conflict behavior
- idempotency key strategy
- verification result
- next node recommendation

- [ ] **Step 4: Commit and push branch**

```powershell
git add backend docs
git commit -m "feat: resume approved workflow publishing"
git push -u origin codex/node-10-approval-resume-publish
```
