# Agent Boundaries and Security Isolation Implementation Plan

**Goal:** Add code-level Agent boundaries, tool permissions, tenant isolation checks, approval-aware access decisions, and a LangGraph-oriented directory contract so each Agent has explicit production-safe limits and a clear place for state, nodes, routes, tools, MCP connectors, and skills.

**Architecture:** Define agent profiles as data, not prompt-only instructions. A boundary policy validates every planned tool call against the agent role, tenant context, tool risk level, approval state, permission set, and secret-exposure rules. The repository uses a LangGraph-style layout where shared state, nodes, route decisions, tool wrappers, MCP connectors, and skills live in separate modules with explicit interfaces. API routes expose profiles and dry-run access decisions for debugging and future UI use.

**Tech Stack:** Python, FastAPI, Pydantic, pytest.

## Global Constraints

- Agent boundaries must be enforced in backend code, not only documented in prompts.
- Agents cannot directly access databases, secrets, or platform adapters.
- Agents can only request typed tools registered in `ToolRegistry`.
- High-risk and critical-risk tools require approval before execution.
- Tenant-scoped tool calls must reject cross-tenant access.
- LLM-visible context must never include raw API keys or secret-like fields.
- LangGraph node functions should return state updates rather than mutating state in place.
- Route functions should be deterministic and should not execute business side effects.
- Tests must not require real SiliconFlow calls or external services.

## File Structure

- `backend/app/domain/enums.py`: add `AgentRole`.
- `backend/app/agents/profiles.py`: define `AgentProfile` and default profiles for each PRD Agent.
- `backend/app/agents/graphs/state.py`: define `CommerceAgentState` and state factory.
- `backend/app/agents/graphs/nodes/base.py`: define node metadata and side-effect boundary categories.
- `backend/app/agents/graphs/routes/base.py`: define route decision schema and approval route helper.
- `backend/app/agents/mcp/registry.py`: define MCP connector metadata registry.
- `backend/app/agents/skills/registry.py`: define agent skill metadata registry.
- `backend/app/agents/prompts/registry.py`: define versioned prompt metadata registry.
- `backend/app/agents/checkpoints/policy.py`: define checkpoint and human approval interrupt policies.
- `backend/app/agents/observability/schema.py`: define trace event schema for node, tool, approval, evaluation, and error events.
- `backend/app/agents/evaluation/registry.py`: define evaluation scenario metadata.
- `backend/app/agents/memory/policy.py`: define workflow, tenant, and global memory boundaries.
- `backend/app/security/boundary.py`: define `ToolAccessContext`, `ToolAccessDecision`, and `AgentBoundaryPolicy`.
- `backend/app/api/routes/agents.py`: expose profile listing and dry-run tool access checks.
- `backend/app/main.py`: register agent routes.
- `backend/tests/test_agent_boundaries.py`: verify agent-specific tool boundaries.
- `backend/tests/test_security_isolation.py`: verify tenant isolation, approval gating, and secret redaction.
- `backend/tests/test_langgraph_contract.py`: verify state, node, route, mcp, and skill contracts.
- `backend/tests/test_agent_engineering_contract.py`: verify prompt, checkpoint, observability, evaluation, and memory best-practice contracts.
- `README.md`: document the new boundary layer.

## Tasks

### Task 1: Agent roles and profiles

- Add `AgentRole` values for supervisor, product research, profit analyst, supplier, listing, localization, ops, customer support, and risk review.
- Define profile fields:
  - `role`
  - `display_name`
  - `purpose`
  - `allowed_tools`
  - `max_risk_level`
  - `can_request_approval`
  - `tenant_scoped`
  - `forbidden_data_classes`
- Test that Listing Agent can draft and validate listings but cannot publish listings.
- Test that Customer Support Agent can draft support responses but cannot issue refunds.

### Task 2: LangGraph directory and interface contract

- Add `CommerceAgentState` as a TypedDict with fields:
  - `workflow_id`
  - `tenant_id`
  - `current_agent`
  - `current_step`
  - `messages`
  - `tool_calls`
  - `approval_required`
  - `approval_request_id`
  - `risk_level`
  - `evidence`
  - `errors`
- Add node metadata registry for node names and whether a node is read-only, deterministic, or approval-gated.
- Add route decisions for continue, await_approval, retry, fail, and complete.
- Add MCP connector metadata registry placeholders without real external calls.
- Add skill metadata registry placeholders for domain-specific instructions.

### Task 3: Security boundary policy

- Implement `AgentBoundaryPolicy.evaluate_tool_access`.
- Check:
  - agent role exists
  - tool exists
  - tool is in agent profile `allowed_tools`
  - requested tenant matches actor tenant
  - required permission is present
  - high/critical risk tool has approval
  - secret-like payload keys are rejected
- Return structured decision instead of raising for normal policy denial.

### Task 4: Prompt, checkpoint, observability, evaluation, and memory contracts

- Add versioned prompt metadata with required and forbidden context keys.
- Add checkpoint policy metadata for read-only snapshots, human approval interrupts, and retryable failures.
- Add trace event schema containing workflow, tenant, agent, event type, and metadata.
- Add evaluation scenarios for listing claim safety, support RAG groundedness, and workflow approval correctness.
- Add memory policies for workflow, tenant, and global scopes.

### Task 5: Agent API route

- Add `GET /agents/profiles`.
- Add `POST /agents/access-check`.
- Keep this API as dry-run validation only; it must not execute tools.

### Task 6: Verification and progress log

- Run full backend test suite.
- Commit implementation.
- Add `docs/progress/2026-07-10-node-07-agent-boundaries-security-isolation.md`.
- Commit progress log.
- Push to `origin/main`.
