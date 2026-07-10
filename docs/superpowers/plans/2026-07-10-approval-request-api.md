# Approval Request API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the product-launch `await_approval` graph stop into a queryable, approvable, rejectable approval request workflow for the MVP.

**Architecture:** Add a small approval domain model and an in-memory repository with idempotent request creation. The LangGraph `await_approval` node creates or reuses a pending approval request at the explicit approval checkpoint; conditional route functions stay pure and side-effect free. FastAPI exposes approval listing, detail, approve, and reject endpoints for the future operator UI.

**Tech Stack:** Python, FastAPI, Pydantic, pytest, LangGraph.

## Global Constraints

- No real marketplace publish is executed in Node 09.
- Approval creation must be idempotent for the same `approval_request_id`.
- Approval transitions must reject invalid cross-terminal changes, for example approved -> rejected.
- Missing approval IDs return HTTP 404.
- Conflicting approval transitions return HTTP 409.
- Tests must not require real SiliconFlow calls or external services.
- Routes under `backend/app/agents/graphs/routes/` remain deterministic and side-effect free.
- Every completed node must add a summary log under `docs/progress/`.

---

## File Structure

- Create `backend/app/domain/approvals.py`: approval request entity, action request, and response models.
- Create `backend/app/repositories/__init__.py`: repository package marker.
- Create `backend/app/repositories/approvals.py`: in-memory approval repository and transition errors.
- Create `backend/app/api/routes/approvals.py`: approval API endpoints.
- Modify `backend/app/agents/graphs/state.py`: add `approval_request` metadata to workflow state.
- Modify `backend/app/agents/graphs/nodes/product_launch.py`: make `await_approval_node` idempotently create an approval request.
- Modify `backend/app/api/routes/workflows.py`: include `approval_request_id` and `approval_request` in workflow preview output.
- Modify `backend/app/main.py`: register approval router.
- Test `backend/tests/test_approval_repository.py`: repository behavior.
- Test `backend/tests/test_approvals_api.py`: HTTP behavior.
- Modify `backend/tests/test_product_launch_graph.py`: graph creates a retrievable approval request.
- Modify `backend/tests/test_workflows_api.py`: workflow response exposes approval request metadata.
- Add `docs/progress/2026-07-10-node-09-approval-request-api.md`: Node 09 summary log.

## Tasks

### Task 1: Approval repository tests

**Files:**
- Create: `backend/tests/test_approval_repository.py`
- Create later: `backend/app/domain/approvals.py`
- Create later: `backend/app/repositories/approvals.py`

**Interfaces:**
- Consumes: `ApprovalStatus` from `backend/app/domain/enums.py`
- Produces:
  - `ApprovalRequest`
  - `ApprovalActionRequest`
  - `ApprovalRepository`
  - `ApprovalConflictError`

- [ ] **Step 1: Write failing repository tests**

```python
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
```

- [ ] **Step 2: Run repository tests to verify they fail**

Run: `python -m pytest tests/test_approval_repository.py -v` from `backend/`

Expected: FAIL because `app.repositories.approvals` does not exist.

- [ ] **Step 3: Implement minimal domain and repository**

Create `ApprovalRequest` with fields:
- `id: str`
- `workflow_id: str`
- `tenant_id: str`
- `requested_by: str`
- `reason_codes: list[str]`
- `risk_level: RiskLevel`
- `resource_type: str`
- `resource_id: str`
- `status: ApprovalStatus`
- `metadata: dict[str, Any]`
- `created_at: datetime`
- `reviewed_at: datetime | None`
- `reviewed_by: str | None`
- `review_comment: str | None`

Implement `ApprovalRepository.upsert_pending`, `get`, `list`, `approve`, `reject`, and `clear`.

- [ ] **Step 4: Run repository tests to verify they pass**

Run: `python -m pytest tests/test_approval_repository.py -v` from `backend/`

Expected: PASS.

### Task 2: Graph approval request integration

**Files:**
- Modify: `backend/app/agents/graphs/state.py`
- Modify: `backend/app/agents/graphs/nodes/product_launch.py`
- Modify: `backend/tests/test_product_launch_graph.py`

**Interfaces:**
- Consumes: `get_approval_repository().upsert_pending(...)`
- Produces: workflow state fields `approval_request_id` and `approval_request`

- [ ] **Step 1: Write failing graph test**

```python
from app.repositories.approvals import get_approval_repository


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
```

- [ ] **Step 2: Run graph test to verify it fails**

Run: `python -m pytest tests/test_product_launch_graph.py::test_product_launch_graph_creates_retrievable_approval_request -v` from `backend/`

Expected: FAIL because graph state does not include persisted approval metadata yet.

- [ ] **Step 3: Implement graph integration**

Add `approval_request: dict[str, Any]` to `CommerceAgentState` and `create_initial_state`.

Update `await_approval_node` to call:
```python
approval = get_approval_repository().upsert_pending(
    approval_id=f"appr_{state['workflow_id']}",
    workflow_id=state["workflow_id"],
    tenant_id=state["tenant_id"],
    requested_by=AgentRole.SUPERVISOR.value,
    reason_codes=state["approval_reasons"],
    risk_level=state["risk_level"],
    resource_type="workflow",
    resource_id=state["workflow_id"],
    metadata={
        "tool": "publish_listing",
        "product_idea": state["product_idea"],
        "target_marketplaces": state["target_marketplaces"],
    },
)
```

Return `approval_request_id` and `approval_request` from the node.

- [ ] **Step 4: Run graph tests to verify they pass**

Run: `python -m pytest tests/test_product_launch_graph.py -v` from `backend/`

Expected: PASS.

### Task 3: Approval HTTP API

**Files:**
- Create: `backend/app/api/routes/approvals.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_approvals_api.py`

**Interfaces:**
- Consumes: `get_approval_repository()`
- Produces:
  - `GET /approvals`
  - `GET /approvals/{approval_id}`
  - `POST /approvals/{approval_id}/approve`
  - `POST /approvals/{approval_id}/reject`

- [ ] **Step 1: Write failing API tests**

```python
from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.approvals import get_approval_repository


def test_approval_api_lists_gets_and_approves_request():
    repo = get_approval_repository()
    repo.clear()
    client = TestClient(create_app())

    workflow_response = client.post(
        "/workflows",
        json={
            "product_idea": "foldable under-bed storage organizer",
            "target_marketplaces": ["amazon"],
            "target_price": 29.99,
            "risk_preference": "balanced",
        },
    )
    approval_id = workflow_response.json()["approval_request_id"]

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
    client = TestClient(create_app())

    missing = client.get("/approvals/appr_missing")
    assert missing.status_code == 404

    workflow_response = client.post(
        "/workflows",
        json={
            "product_idea": "foldable under-bed storage organizer",
            "target_marketplaces": ["amazon"],
            "target_price": 29.99,
            "risk_preference": "balanced",
        },
    )
    approval_id = workflow_response.json()["approval_request_id"]
    client.post(f"/approvals/{approval_id}/reject", json={"reviewer_id": "ops-lead"})

    conflict = client.post(f"/approvals/{approval_id}/approve", json={"reviewer_id": "ops-lead"})
    assert conflict.status_code == 409
```

- [ ] **Step 2: Run API tests to verify they fail**

Run: `python -m pytest tests/test_approvals_api.py -v` from `backend/`

Expected: FAIL because `/approvals` routes are not registered.

- [ ] **Step 3: Implement API route**

Use `APIRouter(prefix="/approvals", tags=["approvals"])`.

Endpoint behavior:
- `GET /approvals` returns `{"approvals": [request...]}`.
- `GET /approvals/{approval_id}` returns the request or 404.
- `POST /approvals/{approval_id}/approve` returns approved request, 404 if missing, 409 on conflict.
- `POST /approvals/{approval_id}/reject` returns rejected request, 404 if missing, 409 on conflict.

Register the router in `create_app()`.

- [ ] **Step 4: Run API tests to verify they pass**

Run: `python -m pytest tests/test_approvals_api.py -v` from `backend/`

Expected: PASS.

### Task 4: Workflow response and verification

**Files:**
- Modify: `backend/app/api/routes/workflows.py`
- Modify: `backend/tests/test_workflows_api.py`
- Add: `docs/progress/2026-07-10-node-09-approval-request-api.md`

**Interfaces:**
- Consumes: graph state `approval_request_id` and `approval_request`
- Produces: API response fields `approval_request_id` and `approval_request`

- [ ] **Step 1: Extend workflow API test**

Add assertions:
```python
assert data["approval_request_id"].startswith("appr_")
assert data["approval_request"]["status"] == "pending"
assert data["approval_request"]["workflow_id"] == data["workflow_id"]
```

- [ ] **Step 2: Run workflow API test to verify it fails**

Run: `python -m pytest tests/test_workflows_api.py::test_create_workflow_returns_deterministic_preview -v` from `backend/`

Expected: FAIL because workflow response does not expose approval request fields.

- [ ] **Step 3: Add fields to workflow response**

Return:
```python
"approval_request_id": state["approval_request_id"],
"approval_request": state["approval_request"],
```

- [ ] **Step 4: Run focused and full tests**

Run from `backend/`:
```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_approval_repository.py tests/test_product_launch_graph.py tests/test_approvals_api.py tests/test_workflows_api.py -v
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -v
```

Expected: PASS, with all backend tests green.

- [ ] **Step 5: Add Node 09 progress log**

Document:
- approval domain and repository
- graph approval checkpoint behavior
- API endpoints
- test result
- next node recommendation

- [ ] **Step 6: Commit and push branch**

```powershell
git add backend docs
git commit -m "feat: add approval request api"
git push -u origin codex/node-09-approval-api
```
