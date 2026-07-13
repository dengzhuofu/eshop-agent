# Localization Agent Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Localization Agent 作为 Product Launch LangGraph 主链路中的独立节点接入，使本地化结果进入 state、snapshot、trace、API 响应和风险审查。

**Architecture:** Listing Agent 继续负责生成 marketplace-specific draft；Localization Agent 在 Listing validation 之前执行确定性的 MVP 本地化，输出可审计的 diff-like summary 与 localized draft metadata；Listing validation 使用本地化后的 draft 校验最终上架文本。Risk Review 只读取 localization state 中明确的风险信号，不在 route 中隐藏业务判断。

**Tech Stack:** Python 3.12, FastAPI, LangGraph, Pydantic, pytest, deterministic mock services.

## Global Constraints

- 中文文档和 progress log 优先。
- 每个完成节点必须在 `docs/progress/` 生成总结日志。
- 新功能遵循 TDD：先写失败测试并确认失败，再实现。
- 不泄露 API key，不把 secret 写入代码、PRD、README、trace 或日志。
- `route` 指 LangGraph conditional edge routing，不是 FastAPI HTTP route。
- Agent 边界必须清晰：Localization Agent 只做本地化和风险信号，不执行发布、价格、库存、退款等高风险写操作。
- MVP 不接真实翻译 API，不引入外部网络依赖；用 deterministic mock localization 保证可回放。
- 现有 3 个旧文档文件仅有换行符脏状态，不纳入本节点提交。

---

## File Structure

- Modify `backend/app/agents/graphs/state.py`: 增加 `target_locale`、`localized_listings`、`localization_risk_flags`、`listing_drafts`，并在 initial state 初始化。
- Modify `backend/app/agents/graphs/nodes/product_launch.py`: 提取 draft 构建 helper，新增 `localization_node`，让 listing validation 和 publish 使用本地化 draft。
- Modify `backend/app/agents/graphs/workflows/product_launch.py`: 接入 `localization` graph node，更新 `STEP_AGENT_ROLES` 和 `run_product_launch_preview` 入参。
- Modify `backend/app/agents/graphs/nodes/base.py`: 增加 localization node contract。
- Modify `backend/app/api/routes/workflows.py`: 请求支持 `target_locale`，响应暴露本地化结果。
- Modify `backend/tests/test_product_launch_graph.py`: 覆盖主链路顺序、本地化输出、风险审查、trace role、publish resume 使用 snapshot。
- Modify `backend/tests/test_workflows_api.py`: 覆盖 `POST /workflows` 的 `target_locale` 与 localization response。
- Modify `backend/tests/test_langgraph_contract.py`: 覆盖 initial state 和 node contract。
- Create `docs/progress/2026-07-13-node-14-localization-agent-graph.md`: 节点总结日志。

## Task 1: State, API, and Contract Failing Tests

**Files:**
- Modify: `backend/tests/test_langgraph_contract.py`
- Modify: `backend/tests/test_workflows_api.py`

**Interfaces:**
- Consumes: `create_initial_state(...) -> CommerceAgentState`
- Produces: test expectations for `target_locale`, `localized_listings`, `localization_risk_flags`, and localization contract output keys.

- [ ] **Step 1: Write failing state and contract tests**

Add assertions to `test_initial_langgraph_state_contains_required_agent_fields`:

```python
assert state["target_locale"] == "en-US"
assert state["listing_drafts"] == []
assert state["localized_listings"] == []
assert state["localization_risk_flags"] == []
```

Add assertions to `test_node_contracts_separate_read_only_and_approval_gated_nodes`:

```python
assert contracts["localization"].owner_agent == AgentRole.LOCALIZATION
assert contracts["localization"].side_effect == NodeSideEffect.DETERMINISTIC
assert {
    "listing_drafts",
    "localized_listings",
    "localization_risk_flags",
    "tool_calls",
    "evidence",
}.issubset(contracts["localization"].output_keys)
```

- [ ] **Step 2: Write failing API test expectations**

Update `WORKFLOW_REQUEST` in `backend/tests/test_workflows_api.py`:

```python
"target_locale": "en-GB",
```

Add assertions in `test_create_workflow_returns_deterministic_preview`:

```python
assert data["target_locale"] == "en-GB"
assert len(data["localized_listings"]) == 3
assert all(item["locale"] == "en-GB" for item in data["localized_listings"])
assert any("unit_style" in item["changes"] for item in data["localized_listings"])
assert data["localization_risk_flags"] == []
```

- [ ] **Step 3: Run focused tests to verify RED**

Run:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_langgraph_contract.py::test_initial_langgraph_state_contains_required_agent_fields tests/test_langgraph_contract.py::test_node_contracts_separate_read_only_and_approval_gated_nodes tests/test_workflows_api.py::test_create_workflow_returns_deterministic_preview -v
```

Expected: FAIL because state/API/contract fields do not exist yet.

## Task 2: Localization State and Graph Node

**Files:**
- Modify: `backend/app/agents/graphs/state.py`
- Modify: `backend/app/agents/graphs/nodes/base.py`
- Modify: `backend/app/agents/graphs/nodes/product_launch.py`
- Modify: `backend/app/agents/graphs/workflows/product_launch.py`

**Interfaces:**
- Consumes: `CommerceAgentState`, `ListingDraft`, `Marketplace`
- Produces:
  - `localization_node(state: CommerceAgentState) -> dict`
  - state key `listing_drafts: list[dict[str, Any]]`
  - state key `localized_listings: list[dict[str, Any]]`
  - state key `localization_risk_flags: list[dict[str, Any]]`
  - state key `target_locale: str`

- [ ] **Step 1: Extend state**

In `CommerceAgentState`, add:

```python
target_locale: str
listing_drafts: list[dict[str, Any]]
localized_listings: list[dict[str, Any]]
localization_risk_flags: list[dict[str, Any]]
```

In `create_initial_state`, add parameter:

```python
target_locale: str = "en-US",
```

Initialize:

```python
"target_locale": target_locale,
"listing_drafts": [],
"localized_listings": [],
"localization_risk_flags": [],
```

- [ ] **Step 2: Add deterministic localization node**

Add helpers in `backend/app/agents/graphs/nodes/product_launch.py`:

```python
def _drafts_for_state(state: CommerceAgentState) -> list[ListingDraft]:
    existing = state.get("localized_listings") or state.get("listing_drafts") or []
    if existing:
        return [ListingDraft.model_validate(item["draft"]) for item in existing if "draft" in item]
    return [
        _draft_for_marketplace(Marketplace(marketplace_value), state)
        for marketplace_value in state["target_marketplaces"]
    ]
```

Add `localization_node`:

```python
def localization_node(state: CommerceAgentState) -> dict:
    locale = state["target_locale"]
    listing_drafts = [_draft_for_marketplace(Marketplace(value), state) for value in state["target_marketplaces"]]
    localized = []
    risk_flags = []
    for draft in listing_drafts:
        localized_draft = draft.model_copy(update={"locale": locale})
        changes = ["locale"]
        if locale == "en-GB":
            localized_draft.attributes["unit_style"] = "metric"
            localized_draft.attributes["market_wording"] = "UK English"
            changes.extend(["unit_style", "market_wording"])
        localized.append(
            {
                "marketplace": draft.marketplace.value,
                "source_sku": draft.sku,
                "locale": locale,
                "changes": changes,
                "risk_flags": [],
                "draft": localized_draft.model_dump(mode="json"),
            }
        )
    return {
        "current_agent": AgentRole.LOCALIZATION,
        "current_step": WorkflowState.LOCALIZING,
        "completed_steps": _append_step(state, "localization"),
        "listing_drafts": [draft.model_dump(mode="json") for draft in listing_drafts],
        "localized_listings": localized,
        "localization_risk_flags": risk_flags,
        "tool_calls": [
            *state["tool_calls"],
            {
                "tool": "localize_listing",
                "locale": locale,
                "risk_level": RiskLevel.MEDIUM.value,
                "status": "completed",
            },
        ],
        "evidence": [
            *state["evidence"],
            {
                "source": "mock_localization_rules",
                "summary": f"Localized {len(localized)} listing drafts for {locale}.",
                "confidence": 0.84,
            },
        ],
    }
```

Use `_drafts_for_state(state)` inside `listing_validation_node` and `publish_listing_node` so validation/publish operate on localized drafts when available.

- [ ] **Step 3: Wire graph**

Update imports and graph:

```python
graph.add_node("localization", localization_node)
graph.add_edge("supplier_evaluation", "localization")
graph.add_edge("localization", "listing_validation")
```

Update `STEP_AGENT_ROLES`:

```python
"localization": AgentRole.LOCALIZATION,
```

Update `run_product_launch_preview` signature and call to `create_initial_state` with `target_locale`.

- [ ] **Step 4: Run focused tests to verify GREEN for Task 1**

Run the same focused command from Task 1.

Expected: PASS.

## Task 3: Graph Behavior, Risk Review, Trace, and Publish Resume Tests

**Files:**
- Modify: `backend/tests/test_product_launch_graph.py`
- Modify: `backend/app/agents/graphs/nodes/product_launch.py`
- Modify: `backend/app/agents/graphs/workflows/product_launch.py`
- Modify: `backend/app/api/routes/workflows.py`

**Interfaces:**
- Consumes: `run_product_launch_preview(..., target_locale: str = "en-US")`
- Produces: localized listing outputs in preview state and API response.

- [ ] **Step 1: Write failing graph tests**

Add test in `backend/tests/test_product_launch_graph.py`:

```python
def test_product_launch_graph_records_localization_before_validation():
    state = run_product_launch_preview(
        workflow_id="wf_localization",
        tenant_id="tenant-a",
        product_idea="foldable under-bed storage organizer",
        target_marketplaces=[Marketplace.AMAZON, Marketplace.SHOPIFY],
        target_price=29.99,
        risk_preference="balanced",
        target_locale="en-GB",
    )

    assert state["completed_steps"].index("localization") > state["completed_steps"].index(
        "supplier_evaluation"
    )
    assert state["completed_steps"].index("localization") < state["completed_steps"].index(
        "listing_validation"
    )
    assert len(state["listing_drafts"]) == 2
    assert len(state["localized_listings"]) == 2
    assert all(item["locale"] == "en-GB" for item in state["localized_listings"])
    assert any(call["tool"] == "localize_listing" for call in state["tool_calls"])
```

Add trace assertion in `test_product_launch_preview_records_trace_events`:

```python
assert "localization" in names
localization_event = next(event for event in workflow_events if event.name == "localization")
assert localization_event.agent_role == AgentRole.LOCALIZATION
```

Add snapshot/publish assertion in `test_product_launch_publish_resume_uses_snapshot_not_approval_metadata`:

```python
assert resumed["localized_listings"][0]["locale"] == "en-US"
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_product_launch_graph.py::test_product_launch_graph_records_localization_before_validation tests/test_product_launch_graph.py::test_product_launch_preview_records_trace_events tests/test_product_launch_graph.py::test_product_launch_publish_resume_uses_snapshot_not_approval_metadata -v
```

Expected: FAIL until graph/API resume output exposes localization state.

- [ ] **Step 3: Expose API and resume state**

Update `WorkflowCreateRequest`:

```python
target_locale: str = "en-US"
```

Pass `target_locale=request.target_locale` into `run_product_launch_preview`.

Add create response keys:

```python
"target_locale": state["target_locale"],
"listing_drafts": state["listing_drafts"],
"localized_listings": state["localized_listings"],
"localization_risk_flags": state["localization_risk_flags"],
```

Add resume response keys:

```python
"localized_listings": state["localized_listings"],
```

- [ ] **Step 4: Run focused tests to verify GREEN**

Run:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_product_launch_graph.py tests/test_workflows_api.py tests/test_langgraph_contract.py -v
```

Expected: PASS.

## Task 4: Progress Log, Full Verification, and Commit

**Files:**
- Create: `docs/progress/2026-07-13-node-14-localization-agent-graph.md`

**Interfaces:**
- Consumes: implemented Node 14 diff and test output.
- Produces: durable Chinese node summary log.

- [ ] **Step 1: Create progress log**

The log must include:

```markdown
# 节点 14：Localization Agent 接入 Listing 主链路

时间：2026-07-13
状态：已完成

## 本节点目标
- 将 Localization Agent 接入 Product Launch LangGraph 主链路。
- 让本地化输出进入 state、snapshot、trace、API 响应。
- 保持 MVP deterministic，不接真实翻译服务。

## 已完成内容
- State 扩展
- Localization node
- Graph 主链路更新
- API 更新
- 测试覆盖

## 验证记录
- 后端全量 pytest 通过

## 重要取舍
- 本节点只做确定性本地化 skeleton。
- Localization Agent 不执行发布、价格、库存、退款等高风险操作。
- Risk Review 只读取本地化节点产出的风险标记。

## 下一节点建议
- 节点 15：Listing 草稿版本化与发布 payload 对齐，或进入 Ops Agent mock monitoring。
```

- [ ] **Step 2: Run full backend verification**

Run:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -v
```

Expected: all backend tests pass.

- [ ] **Step 3: Commit Node 14 files only**

Stage only Node 14 paths:

```powershell
git add backend/app/agents/graphs/state.py backend/app/agents/graphs/nodes/base.py backend/app/agents/graphs/nodes/product_launch.py backend/app/agents/graphs/workflows/product_launch.py backend/app/api/routes/workflows.py backend/tests/test_product_launch_graph.py backend/tests/test_workflows_api.py backend/tests/test_langgraph_contract.py docs/superpowers/plans/2026-07-13-localization-agent-graph.md docs/progress/2026-07-13-node-14-localization-agent-graph.md
git commit -m "feat: add localization graph node"
```

- [ ] **Step 4: Push branch and prepare merge**

Run:

```powershell
git push -u origin codex/node-14-localization-agent
```

After push, run final review and then fast-forward merge to `main` if review and tests are clean.
