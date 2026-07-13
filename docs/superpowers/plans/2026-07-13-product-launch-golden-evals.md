# Product Launch 黄金场景与回放评估 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 7 个版本化、无真实模型调用、可回放且可作为 CI 回归门禁的 Product Launch 黄金场景。

**Architecture:** runner 复用现有 preview、snapshot resume 和 publish node，通过加锁的 repository override context 注入独立内存仓储。结果压缩为不含完整 payload 的 `EvaluationResult`；本节点不持久化、不接 API，Node 20 只消费运行结果。

**Tech Stack:** Python 3.12, Pydantic v2, LangGraph 1.2.9, pytest 8.4.1, JSON fixtures, in-memory repositories.

## Global Constraints

- 分支：`codex/node-16-product-launch-golden-evals`，基线必须包含提交 `5cc8bc5`。
- 只创建本计划列出的 Node 16 文件；不修改现有 workflow、node、repository、registry 或公共路由。
- 禁止修改 `backend/app/main.py`、`backend/app/agents/profiles.py`、`backend/app/agents/graphs/state.py`、`backend/app/api/routes/__init__.py`、`backend/app/tools/registry.py`。
- 不调用 SiliconFlow、其他模型、真实 marketplace API 或数据库。
- fixture model 使用 `ConfigDict(extra="forbid")`；每个结果包含非空 `tenant_id`。
- trace/result 只保存 ID、hash、状态、计数、风险和错误类别，不保存完整 listing、message 或 evidence payload。
- 每项 metric 的通过阈值固定为 `1.0`；任何 metric 未通过则回归门禁失败。
- Git 提交描述使用中文；每完成一个可独立评审任务再提交。
- 所有 pytest 命令从 `backend/` 执行，解释器固定为 `C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`。

---

## File Structure

- Create: `backend/app/agents/evaluation/results.py`
- Create: `backend/app/agents/evaluation/runner.py`
- Create: `backend/evals/product_launch/scenarios/*.json`
- Create: `backend/evals/product_launch/expected/*.json`
- Create: `backend/tests/test_product_launch_golden.py`
- Create: `docs/progress/2026-07-13-node-16-product-launch-golden-evals.md`

## Frozen Interfaces

```python
class EvaluationMetric(BaseModel):
    name: str
    score: float = Field(ge=0, le=1)
    threshold: float = Field(default=1.0, ge=0, le=1)
    passed: bool
    reason: str


class EvaluationResult(BaseModel):
    schema_version: Literal["evaluation-result/v1"]
    evaluation_id: str
    scenario_id: str
    scenario_version: int
    tenant_id: str
    workflow_id: str
    status: Literal["passed", "failed"]
    score: float = Field(ge=0, le=1)
    threshold: float = 1.0
    metrics: list[EvaluationMetric]
    expected_summary_hash: str
    actual_summary_hash: str
    actual_summary: ProductLaunchEvaluationSummary
    failure_reasons: list[str]


def load_product_launch_scenario(path: Path) -> ProductLaunchScenario: ...
def load_product_launch_expectation(path: Path) -> ProductLaunchExpectation: ...
def discover_product_launch_fixture_pairs(root: Path = DEFAULT_EVAL_ROOT) -> list[tuple[Path, Path]]: ...
def run_product_launch_scenario(scenario: ProductLaunchScenario, expected: ProductLaunchExpectation) -> EvaluationResult: ...
def run_product_launch_suite(root: Path = DEFAULT_EVAL_ROOT) -> list[EvaluationResult]: ...
def assert_product_launch_regression_gate(results: Sequence[EvaluationResult]) -> None: ...
```

`ProductLaunchEvaluationSummary` 固定包含 identity、final state、risk/profit/supplier、approval、snapshot、validation、selected listing version ID/hash/stage、publish summary、errors、trace counts 和 publish trace statuses。

指标固定为：`identity_match`、`state_and_risk_match`、`approval_and_snapshot_match`、`listing_version_match`、`validation_match`、`publish_match`、`trace_match`、`error_match`。

## Scenario Catalog

Expected JSON 写入完整 hash 和显式 version ID，不允许 runner 从 actual 动态生成 expected。

| Stem | Action | 核心预期 |
|---|---|---|
| `v1-three-platform-approved-publish` | `approve_and_resume` | completed；3 validation；6 versions；3 published；publish IDs 为 `AMAZON-2fd3bc8059`、`SHOPIFY-eb5e767d9e`、`TIKTOK_SHOP-7cfa428ece` |
| `v1-low-profit` | `preview` | awaiting_approval；risk high；Amazon hash `623cf8e9440f02aa1be0b165cf314ca4c5ed0b1197075da22603b01b3b7ce7f2` |
| `v1-high-risk-supplier` | `preview` | supplier high；selected supplier null；approval reasons 为 `publish_listing,supplier_risk` |
| `v1-localization-claim` | `preview` | localization risk count 1；Shopify validation true；hash `8eae7ce985e4d7429ba285364fe4953ad7ea261338dad475a7840ab59100c471` |
| `v1-missing-approval` | `remove_approval_then_publish` | failed；`approval request not found`；零发布 |
| `v1-tampered-version-hash` | `tamper_approval_hash_then_resume` | failed；`approved listing version hash mismatch`；零 publish tool call |
| `v1-adapter-validation-failure` | `approve_and_resume` | failed；version stage `publish_failed`；一条 failed publish trace；hash `485a9dae039253cfc20b04a2d33e1a29fe8ac4550594eeb6e396d67ff5989b61` |

三平台正常场景的 selected hashes 固定为：

```text
amazon      45c27f0f8da5c78a4ec91a08ed2277b71979a1b92acdf979ba162b737b358b44
shopify     e5c5017d639fcccad68cdd715d37e4045c22f02037c6600c836934fe2f061293
tiktok_shop f07756f6749b0178eed6d3f317b86b054c7da8778984430d0b5ded26c35a8cff
```

### Task 1: Evaluation Result Contracts

**Files:** Create `backend/app/agents/evaluation/results.py`; create `backend/tests/test_product_launch_golden.py`.

- [x] **Step 1: Write RED tests**

Add `test_evaluation_result_is_tenant_scoped_and_score_bounded` and `test_evaluation_summary_hash_is_canonical_and_deterministic`.

- [x] **Step 2: Verify RED**

Run from `backend/`:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_product_launch_golden.py -k "evaluation_result or summary_hash" -v
```

Expected: collection fails because `results.py` does not exist.

- [x] **Step 3: Implement GREEN**

Implement strict result/summary models and `canonical_summary_hash(summary) -> str` using sorted compact JSON and SHA-256.

- [x] **Step 4: Verify and commit**

Re-run the focused command; expected PASS. Commit: `feat: 增加 Product Launch 评估结果模型`.

### Task 2: Versioned Fixtures And Loader

**Files:** Create `backend/evals/product_launch/scenarios/*.json`; create `backend/evals/product_launch/expected/*.json`; modify `backend/app/agents/evaluation/runner.py`; modify test.

- [ ] **Step 1: Write RED tests** for exactly seven sorted pairs; malformed JSON; unknown fields; empty/duplicate marketplaces; non-positive price; orphan scenario/expected; duplicate `(scenario_id, version)`; mismatched IDs/versions.
- [ ] **Step 2: Verify RED** with `pytest tests/test_product_launch_golden.py -k "fixture or loader or discover" -v`; expected FAIL.
- [ ] **Step 3: Implement GREEN** with strict `ProductLaunchScenario`, `ProductLaunchExpectation`, `EvaluationFixtureError`, loaders and pair discovery.
- [ ] **Step 4: Verify and commit**; expected PASS. Commit: `feat: 增加版本化 Product Launch 黄金场景夹具`.

### Task 3: Isolated Replay Runner

**Files:** Modify `backend/app/agents/evaluation/runner.py`; modify test.

- [ ] **Step 1: Write RED tests** for seven scenario outcomes, deterministic replay, no-network execution and workflow exceptions normalized to failed `EvaluationResult`.
- [ ] **Step 2: Verify RED** with `pytest tests/test_product_launch_golden.py -k "suite or scenario or replay or network" -v`; expected FAIL.
- [ ] **Step 3: Implement GREEN**. `ProductLaunchEvaluationRepositories` owns fresh Approval/Snapshot/Trace repositories. A process lock and `contextmanager` patch workflow getters and listing approval getter, then restore them in `finally`.
- [ ] **Step 4: Verify and commit**; expected PASS. Commit: `feat: 增加 Product Launch 黄金场景回放运行器`.

### Task 4: Repository Isolation And Regression Gate

**Files:** Modify runner and test.

- [ ] **Step 1: Write RED tests** that seed sentinels in global repositories, execute success and exception scenarios, and prove global state remains unchanged. Add a metric-regression case that must raise `EvaluationGateError`.
- [ ] **Step 2: Verify RED** with `pytest tests/test_product_launch_golden.py -k "isolation or regression_gate" -v`; expected FAIL.
- [ ] **Step 3: Implement GREEN**. The gate requires every result status passed, every metric passed and score `>= 1.0`; fixture execution always restores getter bindings.
- [ ] **Step 4: Verify and commit**; expected PASS. Commit: `test: 增加黄金场景隔离与回归门禁`.

### Task 5: Documentation And Quality Gates

**Files:** Create `docs/progress/2026-07-13-node-16-product-launch-golden-evals.md`.

- [ ] Run `pytest tests/test_product_launch_golden.py -v`.
- [ ] Run `pytest tests/test_product_launch_golden.py tests/test_product_launch_graph.py tests/test_workflow_snapshots.py tests/test_trace_events.py tests/test_agent_engineering_contract.py -v`.
- [ ] Run full `pytest -v` and repository-root `git diff --check`.
- [ ] Request independent code review against this plan, the shared design and ADR 0002; resolve every Critical/Important issue.
- [ ] Write the Chinese progress log with scenario catalog, repository isolation, result contract, TDD evidence, real test counts, review outcome and Node 20 boundary.
- [ ] Commit and push: `docs: 记录第十六节点黄金场景评估进展`; `git push -u origin codex/node-16-product-launch-golden-evals`.
