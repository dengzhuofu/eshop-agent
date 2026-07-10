# LangGraph Workflow Skeleton Implementation Plan

**Goal:** Turn the existing Agent contracts into a runnable LangGraph skeleton for the MVP product-launch workflow.

**Architecture:** Use `StateGraph(CommerceAgentState)` with deterministic node functions. The first graph runs product research, profit analysis, listing validation, risk review, and then routes to `await_approval` when publishing would require human approval. The graph does not execute real external writes or real LLM calls.

**Tech Stack:** Python, LangGraph, FastAPI, Pydantic, pytest.

## Global Constraints

- Graph nodes return state updates and do not mutate input state in place.
- Route functions decide the next node only; they do not call tools or perform side effects.
- `publish_listing` remains approval-gated and is not executed by the skeleton.
- The graph must be deterministic and testable without a real SiliconFlow key.
- Workflow state must retain tenant, evidence, tool call, validation, risk, and approval context.

## File Structure

- `backend/app/agents/graphs/state.py`: extend `CommerceAgentState` with product launch workflow fields.
- `backend/app/agents/graphs/nodes/product_launch.py`: deterministic node functions.
- `backend/app/agents/graphs/routes/product_launch.py`: route helpers for approval and completion.
- `backend/app/agents/graphs/workflows/product_launch.py`: `build_product_launch_graph` and `run_product_launch_preview`.
- `backend/app/api/routes/workflows.py`: call graph runner instead of duplicating workflow logic.
- `backend/tests/test_product_launch_graph.py`: graph-level tests.
- `backend/tests/test_workflows_api.py`: ensure API still returns graph-backed preview.

## Tasks

### Task 1: Graph tests

- Test graph reaches `awaiting_approval`.
- Test graph records ordered node steps.
- Test graph records product research evidence.
- Test graph records profit estimate.
- Test graph records listing validations for all requested marketplaces.
- Test graph records risk review and approval reason `publish_listing`.

### Task 2: State extension

- Add optional workflow fields:
  - `product_idea`
  - `target_marketplaces`
  - `target_price`
  - `risk_preference`
  - `profit_estimate`
  - `listing_validations`
  - `approval_reasons`
  - `completed_steps`

### Task 3: Node functions

- `product_research_node`
- `profit_analysis_node`
- `listing_validation_node`
- `risk_review_node`
- `await_approval_node`
- `complete_node`

### Task 4: Graph builder

- Create `StateGraph(CommerceAgentState)`.
- Add nodes.
- Add edges:
  - START -> product_research
  - product_research -> profit_analysis
  - profit_analysis -> listing_validation
  - listing_validation -> risk_review
  - risk_review -> conditional route
  - await_approval -> END
  - complete -> END

### Task 5: API integration

- Refactor `POST /workflows` to call `run_product_launch_preview`.
- Preserve existing API response shape.

### Task 6: Verification and log

- Run full backend tests.
- Commit implementation.
- Add node 08 progress log.
- Push to `origin/main`.
