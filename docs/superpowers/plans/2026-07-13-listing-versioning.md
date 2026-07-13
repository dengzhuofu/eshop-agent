# Listing Versioning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Product Launch Agent 增加刊登草稿版本化，让审批、快照恢复、发布结果和 trace 都能证明“发布的就是被审批的那一版 listing”。

**Architecture:** `listing_versions` 作为 graph state 中的业务 artifact，由 localization/listing validation 节点产生和更新；approval metadata 只保存轻量版本索引、内容哈希和摘要；publish 节点从 snapshot state 中取完整版本，并用 approval metadata 校验版本 ID 与内容哈希后再发布。Marketplace adapter 继续只接收 `ListingDraft`，版本治理留在 agent harness 层。

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, LangGraph `StateGraph`, pytest, in-memory approval/snapshot/trace repositories.

## Global Constraints

- 保留 `listing_drafts`、`localized_listings`、`listing_validations`、`publish_results` 的兼容输出。
- 新增 `listing_versions`、`selected_listing_version_ids`、`approved_listing_version_ids` 到 `CommerceAgentState`。
- `approval_request.metadata` 不写完整 listing payload，只写 `listing_version_ids`、`listing_version_hashes`、`listing_version_summary`、`publish_diff_summary`。
- `publish_results` 与 publish tool trace 必须包含 `listing_version_id` 和 `listing_content_hash`。
- 真实发布仍必须经过 approval/checkpoint；route 不执行副作用。
- 避免继续膨胀 `backend/app/agents/graphs/nodes/product_launch.py`，listing/localization/publish 相关 helper 放入独立模块。
- 复杂恢复和审批边界逻辑使用中文注释，普通赋值和显而易见代码不加噪音注释。
- 每个完成节点必须新增中文进度日志到 `docs/progress/`。

---

### Task 1: Listing Version Domain Helpers

**Files:**
- Modify: `backend/app/domain/schemas.py`
- Create: `backend/app/services/listing_versions.py`
- Test: `backend/tests/test_langgraph_contract.py`

**Interfaces:**
- Consumes: `ListingDraft`, `Marketplace`
- Produces:
  - `ListingVersion` Pydantic model
  - `create_listing_version(...) -> dict`
  - `listing_version_summary(version: dict) -> dict`
  - `content_hash_for_draft(draft: ListingDraft) -> str`

- [x] **Step 1: Write failing contract assertions**

Add assertions that initial state has empty `listing_versions`, `selected_listing_version_ids`, and `approved_listing_version_ids`; localization/listing validation/publish contracts declare version-related output keys.

- [x] **Step 2: Run failing test**

Run: `python -m pytest tests/test_langgraph_contract.py -v` from `backend/`
Expected: FAIL because state and contracts do not yet expose listing version fields.

- [x] **Step 3: Add schema and helper implementation**

Implement deterministic content hash generation from canonical JSON, stable version IDs derived from workflow, marketplace, version number and hash, and compact approval-safe summaries.

- [x] **Step 4: Run contract test**

Run: `python -m pytest tests/test_langgraph_contract.py -v`
Expected: PASS.

### Task 2: Version-Aware Listing Nodes

**Files:**
- Create: `backend/app/agents/graphs/nodes/listings.py`
- Modify: `backend/app/agents/graphs/nodes/product_launch.py`
- Modify: `backend/app/agents/graphs/workflows/product_launch.py`
- Test: `backend/tests/test_product_launch_graph.py`

**Interfaces:**
- Consumes: `listing_versions`, `selected_listing_version_ids`, approval repository, marketplace adapters
- Produces:
  - `localization_node(state) -> dict` with versioned draft/localized outputs
  - `listing_validation_node(state) -> dict` with validation linked to `listing_version_id`
  - `publish_listing_node(state) -> dict` that publishes only approval-bound versions

- [x] **Step 1: Write failing graph tests**

Add tests proving preview creates listing versions, validation rows link to versions, approval metadata carries version IDs/hashes/summaries, snapshot saves them, publish result and tool events point back to the approved versions, and tampered version hash fails before publish.

- [x] **Step 2: Run failing graph tests**

Run focused pytest commands for the new/changed tests.
Expected: FAIL because `listing_versions` does not exist yet.

- [x] **Step 3: Move listing/localization/publish logic to `nodes/listings.py`**

Keep product research/profit/supplier/risk/approval/complete in `product_launch.py`. Import listing nodes directly from the new module in workflow builder.

- [x] **Step 4: Implement version-aware node behavior**

Localization creates base draft versions and localized versions. Listing validation updates the selected localized versions with validation metadata. Publish resolves approval-bound versions from snapshot state, validates ID/hash, uses idempotency key `{approval_id}:{listing_version_id}:{marketplace}`, and appends version metadata to results and tool calls.

- [x] **Step 5: Run graph tests**

Run: `python -m pytest tests/test_product_launch_graph.py -v`
Expected: PASS.

### Task 3: API Surface And Trace Summaries

**Files:**
- Modify: `backend/app/api/routes/workflows.py`
- Modify: `backend/app/agents/graphs/workflows/product_launch.py`
- Test: `backend/tests/test_workflows_api.py`

**Interfaces:**
- Consumes: graph state with listing versions
- Produces: API responses and trace metadata exposing compact version information

- [x] **Step 1: Write failing API tests**

Assert create/resume responses include `listing_versions`, `selected_listing_version_ids`, `approved_listing_version_ids`, and publish results include version metadata. Assert snapshot response includes selected listing version IDs.

- [x] **Step 2: Run failing API tests**

Run: `python -m pytest tests/test_workflows_api.py -v`
Expected: FAIL because API does not expose version fields yet.

- [x] **Step 3: Add API fields and trace summary metadata**

Expose full `listing_versions` in MVP API responses for developer visibility, but keep trace metadata compact with version IDs, marketplace, locale, hash, and validation status.

- [x] **Step 4: Run API tests**

Run: `python -m pytest tests/test_workflows_api.py -v`
Expected: PASS.

### Task 4: Documentation, Verification, Merge

**Files:**
- Create: `docs/progress/2026-07-13-node-15-listing-versioning.md`

**Interfaces:**
- Consumes: final implementation and test output
- Produces: Chinese progress log for Node 15

- [x] **Step 1: Write progress log**

Document business purpose, implementation scope, agent harness alignment, TDD evidence, and known next steps.

- [x] **Step 2: Run full backend suite**

Run: `python -m pytest -v` from `backend/`
Expected: all tests pass.

- [x] **Step 3: Request code review**

Ask a reviewer subagent to inspect Node 15 against this plan, ADR 0002, and the diff.

- [x] **Step 4: Commit, push, merge to main**

Commit the branch, push it, fast-forward or merge into `main`, run full backend suite again on `main`, and push `main`.
