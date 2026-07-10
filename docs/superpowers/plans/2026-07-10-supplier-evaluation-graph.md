# Supplier Evaluation Graph Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate Supplier Agent evaluation into the product-launch LangGraph workflow.

**Architecture:** Add `supplier_evaluation` as a deterministic LangGraph node between `profit_analysis` and `listing_validation`. The node uses the existing `score_supplier` service, writes supplier scores and selected supplier state, records tool calls, and feeds supplier risk into `risk_review`. Snapshot and trace already derive from final graph state, so the new node should appear naturally in checkpoint and observability output.

**Tech Stack:** Python, FastAPI, Pydantic, pytest, LangGraph.

## Global Constraints

- Do not call real supplier, ERP, marketplace, or payment APIs.
- Supplier evaluation is deterministic and testable without LLM calls.
- Supplier scoring uses the existing `score_supplier` service.
- Supplier Agent only performs deterministic scoring; it does not publish listings or bypass approval.
- Risk Review must include supplier risk when no acceptable supplier is selected.
- Route functions remain pure.
- Snapshot and trace output must include the new node results.
- Add a Node 13 progress log under `docs/progress/`.

---

## File Structure

- Modify `backend/app/agents/graphs/state.py`: add supplier evaluation fields.
- Modify `backend/app/agents/graphs/nodes/product_launch.py`: add `supplier_evaluation_node` and supplier risk handling.
- Modify `backend/app/agents/graphs/workflows/product_launch.py`: insert supplier node into the product-launch graph and trace role map.
- Modify `backend/app/api/routes/workflows.py`: expose supplier evaluation in workflow response.
- Modify `backend/tests/test_product_launch_graph.py`: graph, trace, snapshot, and risk tests.
- Modify `backend/tests/test_workflows_api.py`: API response tests.
- Add `docs/progress/2026-07-10-node-13-supplier-evaluation-graph.md`: Node 13 summary log.

## Tasks

### Task 1: State and graph behavior tests

**Files:**
- Modify: `backend/tests/test_product_launch_graph.py`
- Modify later: `backend/app/agents/graphs/state.py`
- Modify later: `backend/app/agents/graphs/nodes/product_launch.py`
- Modify later: `backend/app/agents/graphs/workflows/product_launch.py`

**Interfaces:**
- Produces state fields:
  - `supplier_evaluations: list[dict[str, Any]]`
  - `selected_supplier_id: str | None`
  - `supplier_risk_level: str`

- [ ] **Step 1: Write failing graph tests**

Add assertions that:
- `completed_steps` includes `supplier_evaluation` between `profit_analysis` and `listing_validation`.
- `supplier_evaluations` contains deterministic scored suppliers.
- `selected_supplier_id` is `SUP-1` for default balanced flow.
- `tool_calls` includes `score_supplier`.
- trace events include `supplier_evaluation` with `AgentRole.SUPPLIER`.

- [ ] **Step 2: Run graph tests to verify they fail**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_product_launch_graph.py -v
```

Expected: FAIL because supplier node is not part of the graph yet.

- [ ] **Step 3: Implement state and supplier node**

Add supplier fields to `CommerceAgentState` and `create_initial_state`.

Add `supplier_evaluation_node`:
- Set `current_agent=AgentRole.SUPPLIER`.
- Set `current_step=WorkflowState.EVALUATING_SUPPLIERS`.
- Score deterministic candidate suppliers through `score_supplier`.
- Select the highest-scoring low-risk recommended supplier when available.
- Set `supplier_risk_level` to selected supplier risk, or `high` if no supplier is recommended.
- Append `supplier_evaluation` to `completed_steps`.
- Append `score_supplier` tool calls.
- Add supplier evidence summary.

Default supplier candidates:
- `SUP-1`: low risk, recommended.
- `SUP-2`: high risk, not recommended.

For `risk_preference="supplier_risk"`, use only high-risk suppliers so Risk Review behavior can be tested deterministically.

- [ ] **Step 4: Insert graph edge**

Update graph:

```text
product_research -> profit_analysis -> supplier_evaluation -> listing_validation
```

Update `STEP_AGENT_ROLES["supplier_evaluation"] = AgentRole.SUPPLIER`.

- [ ] **Step 5: Run graph tests to verify they pass**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_product_launch_graph.py -v
```

Expected: PASS.

### Task 2: Risk Review supplier risk

**Files:**
- Modify: `backend/tests/test_product_launch_graph.py`
- Modify later: `backend/app/agents/graphs/nodes/product_launch.py`

**Interfaces:**
- Consumes: state field `supplier_risk_level`
- Produces: `approval_reasons` includes `supplier_risk` for high supplier risk

- [ ] **Step 1: Write failing risk test**

Add a graph test:

```python
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
    assert "supplier_risk" in state["approval_reasons"]
```

- [ ] **Step 2: Run risk test to verify it fails**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_product_launch_graph.py::test_product_launch_risk_review_flags_high_supplier_risk -v
```

Expected: FAIL because Risk Review does not use supplier risk yet.

- [ ] **Step 3: Update risk review**

Update `risk_review_node`:
- Add `supplier_risk = state["supplier_risk_level"] == "high"`.
- Set overall risk high when listing invalid, profit high, or supplier high.
- Approval reasons always include `publish_listing`.
- Append `supplier_risk` when supplier risk is high.

- [ ] **Step 4: Run graph tests to verify they pass**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_product_launch_graph.py -v
```

Expected: PASS.

### Task 3: API and snapshot visibility

**Files:**
- Modify: `backend/tests/test_workflows_api.py`
- Modify later: `backend/app/api/routes/workflows.py`

**Interfaces:**
- Produces API fields:
  - `supplier_evaluations`
  - `selected_supplier_id`
  - `supplier_risk_level`

- [ ] **Step 1: Write failing API test**

Add assertions to workflow creation response:

```python
assert data["selected_supplier_id"] == "SUP-1"
assert data["supplier_risk_level"] == "low"
assert len(data["supplier_evaluations"]) >= 2
```

- [ ] **Step 2: Run API test to verify it fails**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_workflows_api.py::test_create_workflow_returns_deterministic_preview -v
```

Expected: FAIL because API does not expose supplier state yet.

- [ ] **Step 3: Update API response**

Add supplier fields to `create_workflow` response.

- [ ] **Step 4: Run API tests to verify they pass**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_workflows_api.py -v
```

Expected: PASS.

### Task 4: Verification, progress log, push

**Files:**
- Add: `docs/progress/2026-07-10-node-13-supplier-evaluation-graph.md`

- [ ] **Step 1: Run focused tests**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_product_launch_graph.py tests/test_workflows_api.py tests/test_suppliers.py -v
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
- supplier state fields
- graph node insertion
- risk review behavior
- snapshot/trace/API visibility
- verification result
- next node recommendation

- [ ] **Step 4: Commit and push**

```powershell
git add backend docs
git commit -m "feat: add supplier evaluation graph node"
git push -u origin codex/node-13-supplier-evaluation
```
