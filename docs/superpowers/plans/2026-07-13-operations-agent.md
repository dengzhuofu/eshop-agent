# Node 18 多平台运营读模型与 Ops Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立租户隔离、可回放的多平台运营读模型，让 Ops Agent 基于订单、库存、物流和指标证据识别异常，并且只生成不可执行的动作建议。

**Architecture:** Seeded adapter 实现四类只读查询；service 负责去重、时序归一化、新鲜度、表现汇总、异常和建议；独立 StateGraph 只编排显式状态更新。所有记录绑定 Listing 版本 ID/哈希，Node 20 再负责 API 和跨模块接线。

**Tech Stack:** Python 3.12, Pydantic 2.11.7, LangGraph 1.2.9, pytest 8.4.1, JSON seeded data.

## Global Constraints

- 分支：`codex/node-18-operations-agent`，基线必须包含提交 `5cc8bc5`。
- 禁止修改 `backend/app/main.py`、`backend/app/agents/profiles.py`、`backend/app/agents/graphs/state.py`、公共路由和 `backend/app/tools/registry.py`。
- 只消费现有 `Marketplace`、`AgentRole.OPS`、`RiskLevel`；运营状态、异常和动作类型使用本领域 Literal。
- 每个 event/evidence/anomaly/summary/proposal/failure 都包含 `tenant_id`。
- 每个运营事件携带 `listing_id`、`listing_version_id`、`listing_content_hash`、`sku`。
- 不执行改价、补货、库存预留、发布、退款或客服发送；proposal 固定为 `status="proposed"`、`execution_allowed=False`。
- `as_of` 必须由调用方传入；禁止用当前时间隐式改变回放结果。
- trace summary 只保存 ID、版本、计数、新鲜度、决策和错误代码，不保存完整订单或指标 payload。
- 测试不调用真实模型、平台 API、数据库或 Node 17 executor。
- Git 提交描述使用中文。
- 所有 pytest 命令从 `backend/` 执行，解释器固定为 `C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`。

---

## Files

- Create: `backend/app/domain/operations.py`
- Create: `backend/app/adapters/operations.py`
- Create: `backend/app/mock_data/operations/orders.json`
- Create: `backend/app/mock_data/operations/inventory.json`
- Create: `backend/app/mock_data/operations/shipments.json`
- Create: `backend/app/mock_data/operations/metrics.json`
- Create: `backend/app/services/operations.py`
- Create: `backend/app/agents/graphs/operations/__init__.py`
- Create: `backend/app/agents/graphs/operations/state.py`
- Create: `backend/app/agents/graphs/operations/nodes.py`
- Create: `backend/app/agents/graphs/operations/routes.py`
- Create: `backend/app/agents/graphs/operations/workflow.py`
- Create: `backend/tests/test_operations_agent.py`
- Create: `docs/progress/2026-07-13-node-18-operations-agent.md`

## Frozen Interfaces

```python
OperationsRecord = Annotated[
    OrderEvent | InventoryEvent | ShipmentEvent | MetricEvent,
    Field(discriminator="record_type"),
]


class OperationsReadPort(Protocol):
    def read_orders(self, query: OperationsReadQuery) -> list[OrderEvent]: ...
    def read_inventory(self, query: OperationsReadQuery) -> list[InventoryEvent]: ...
    def read_shipments(self, query: OperationsReadQuery) -> list[ShipmentEvent]: ...
    def read_metrics(self, query: OperationsReadQuery) -> list[MetricEvent]: ...


class SeededOperationsReadAdapter:
    def __init__(self, records: Sequence[OperationsRecord]) -> None: ...
    @classmethod
    def from_directory(cls, directory: Path) -> Self: ...


def get_seeded_operations_read_port(seed_directory: Path | None = None) -> OperationsReadPort: ...
def build_operations_read_model(port: OperationsReadPort, query: OperationsReadQuery,
                                policy: FreshnessPolicy | None = None) -> OperationsReadModel: ...
def summarize_operations(read_model: OperationsReadModel) -> list[OpsPerformanceSummary]: ...
def detect_ops_anomalies(read_model: OperationsReadModel,
                         thresholds: AnomalyThresholds | None = None
                         ) -> tuple[list[OpsAnomaly], list[OpsEvidence]]: ...
def propose_ops_actions(*, workflow_id: str, tenant_id: str,
                        anomalies: list[OpsAnomaly]) -> list[OpsActionProposal]: ...
def create_initial_operations_state(*, workflow_id: str, tenant_id: str,
                                    query: OperationsReadQuery) -> OpsAgentState: ...
def build_operations_graph(port: OperationsReadPort): ...
def run_operations_agent(*, workflow_id: str, tenant_id: str, as_of: datetime,
                         marketplaces: list[Marketplace] | None = None,
                         listing_version_ids: list[str] | None = None,
                         port: OperationsReadPort | None = None) -> OpsAgentState: ...
```

每个事件公共字段：`record_type`、`event_id`、`tenant_id`、`marketplace`、`listing_id`、`listing_version_id`、`listing_content_hash`、`sku`、`observed_at`、`received_at`。

领域字段：

```text
OrderEvent: order_id, status, quantity, gross_revenue, currency
InventoryEvent: available_quantity, reserved_quantity, reorder_point
ShipmentEvent: shipment_id, order_id, status, promised_delivery_at, estimated_delivery_at
MetricEvent: metric_name, value, window_start, window_end
```

模型使用 `ConfigDict(extra="forbid")`，时间必须为 aware datetime，listing hash 为 64 位小写十六进制。

新鲜度上限：订单 86400 秒、库存 21600 秒、物流 21600 秒、指标 172800 秒；迟到阈值 43200 秒。异常阈值：库存 `available_quantity <= reorder_point`；物流延迟至少 24 小时；转化率相对下降至少 20%；退货率绝对上升至少 0.03。

固定回放时间 `2026-07-13T12:00:00Z`。tenant-a：Amazon 制造晚到旧库存与低库存；Shopify 制造物流延迟；TikTok Shop 制造 conversion `0.040 -> 0.028` 和 return rate `0.050 -> 0.090`。tenant-b 为健康对照。

### Task 1: Domain Contracts

**Files:** Create domain/test.

- [x] **Step 1: Write RED tests** `test_operations_models_require_aware_timestamps_and_version_hash` and `test_action_proposal_is_non_executable`.
- [x] **Step 2: Verify RED**:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_operations_agent.py -k "operations_models or action_proposal" -v
```

Expected: collection FAIL because domain module is absent.

- [x] **Step 3: Implement GREEN** with strict models, discriminated union, `Literal["proposed"]`, `Literal[False]` and explicit failure models.
- [x] **Step 4: Verify and commit**; expected PASS. Commit: `feat: 增加运营读模型领域契约`.

### Task 2: Tenant-Scoped Seeded Read Port

**Files:** Create adapter/seeds; modify test.

- [x] **Step 1: Write RED tests** for all four record types, tenant/marketplace/version filters and invalid seed normalization.
- [x] **Step 2: Verify RED** with `pytest tests/test_operations_agent.py -k "seeded_port or seed_loader" -v`; expected FAIL.
- [x] **Step 3: Implement GREEN**. Parse JSON with `TypeAdapter(list[OperationsRecord])`; every read method filters tenant before other fields. Invalid files raise `OperationsReadError(code="seed_validation_failed")` without exposing raw payload.
- [x] **Step 4: Verify and commit**; expected PASS. Commit: `feat: 增加租户隔离运营种子数据`.

### Task 3: Normalization, Freshness, Evidence And Proposals

**Files:** Create service; modify test.

- [x] **Step 1: Write RED tests** for identical duplicate dedupe, conflicting event ID failure, malicious cross-tenant port, hash drift, future event exclusion, late/out-of-order diagnostics, latest observation selection, threshold equality, zero baseline and healthy controls.
- [x] **Step 2: Verify RED** with `pytest tests/test_operations_agent.py -k "read_model or freshness or anomaly or proposal or summary" -v`; expected FAIL.
- [x] **Step 3: Implement GREEN**. Select latest by `(observed_at, received_at, event_id)`; only fresh evidence may produce anomalies. Every evidence/anomaly/proposal preserves source event IDs and listing version identity.
- [x] **Step 4: Implement safe mapping**: low stock -> replenish proposal; shipment delay -> support strategy; conversion drop -> price review plus listing optimization; return rise -> listing optimization. All proposals use `RiskLevel.HIGH`, `approval_required_for_execution=True`, `execution_allowed=False`.
- [x] **Step 5: Verify and commit**; expected PASS. Commit: `feat: 增加运营异常检测与证据建议`.

### Task 4: Independent Ops StateGraph

**Files:** Create operations graph package; modify test.

- [x] **Step 1: Write RED tests** for ordered steps, insufficient data, normalized port failure, trace summaries without payload and deterministic replay IDs.
- [x] **Step 2: Verify RED** with `pytest tests/test_operations_agent.py -k "graph or trace or replay" -v`; expected FAIL.
- [x] **Step 3: Implement GREEN** with `START -> load_operations -> route -> detect_anomalies -> propose_actions -> complete -> END`. Route reads state only; nodes return explicit updates and import no write adapter, approval repository or executor.
- [x] **Step 4: Error semantics**: source/tenant/event/version conflict -> `failed`; all data absent/stale -> `insufficient_data` with no proposals; partially fresh data -> proposals only from fresh evidence.
- [x] **Step 5: Verify and commit**; run complete test file, expected PASS. Commit: `feat: 增加只读 Ops Agent 图`.

### Task 5: Progress Log And Quality Gate

**Files:** Create progress log.

- [ ] Run focused `pytest tests/test_operations_agent.py -v`.
- [ ] Run full `pytest -v` and repository-root `git diff --check`.
- [ ] Request independent review against shared design, PRD section 7.10 and ADR 0002; resolve every Critical/Important issue.
- [ ] Write Chinese progress log with ownership, version linkage, dedupe/freshness, graph flow, safety boundary, TDD evidence, real counts and Node 20 boundary.
- [ ] Confirm `git diff --name-only 5cc8bc5...HEAD` contains only Node 18 files.
- [ ] Commit and push: `docs: 记录第十八节点运营 Agent 进展`; `git push -u origin codex/node-18-operations-agent`.
