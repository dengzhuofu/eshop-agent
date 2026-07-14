# Node 16-19 分支加固与集成实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 关闭 LG16-EVAL-01、LG17-EXEC-01、LG18-OPS-01、LG19-RAG-01，经过独立评审后将四个节点分支安全集成到最新主线。

**Architecture:** Node 16、17、18 使用现有独立 worktree 并行修复；Node 19 先处理不依赖 ToolExecutor 的实体引用和评估门禁，再合并修复后的 Node 17 完成七工具接线。最终以 `dev-com` 为集成分支，按 16、17、18、19 顺序使用 `--no-ff` 合并并逐次验证，`main` 保持不动。

**Tech Stack:** Python 3.12, Pydantic 2.11.7, pytest 8.4.1, LangGraph 1.2.9, Git worktrees.

## Global Constraints

- 最新主线至少包含 `0818561`；四分支共同历史基线为 `106544d7d7dd8585da387c946375ef2f0ad44200`。
- 审计 HEAD 分别为 Node 16 `6cac2a0a3b1b20a87c8ba99c3bbba3143129cd08`、Node 17 `baf88ed4d95aa08cc3ae23e32fac57eb0c25955f`、Node 18 `cf558d222c4ad8b12f4a98eb79e83bba42555027`、Node 19 `7d3ae55922d0ecf63428f3b9124c25424a37428f`。
- 保留现有四个独立 worktree；不同 Agent 不得共享 checkout，不得修改其他节点的所有权文件。
- 主工作区已有三份未提交文档不得暂存、覆盖或格式化。
- 测试命令从各 worktree 的 `backend/` 执行；不读取真实 API key，不调用网络。
- 复杂审批、幂等、订单生命周期和 ACL 逻辑添加必要中文注释；普通代码不写叙述性注释。
- 每项先 RED、再 GREEN；聚焦与全量测试都通过后才提交。Git 提交使用中文描述。
- 每个分支修复完成后由独立 reviewer 检查；任何 Critical/Important 未关闭时禁止集成。
- 四份标准化计划必须先提交并推送 `dev-com`。执行时通过 `git log -1 --format=%H -- docs/superpowers/plans/2026-07-13-node-16-19-hardening-integration.md` 解析 `PLAN_BASE_SHA`，`dev-com` 必须包含该提交；禁止合并或推送 `main`。

---

### Task 1: LG16-EVAL-01 黄金评估门禁

**Files:**
- Modify: `backend/app/agents/evaluation/results.py`
- Modify: `backend/app/agents/evaluation/runner.py`
- Modify: `backend/tests/test_product_launch_golden.py`

**Interfaces:**
- Produces: `PRODUCT_LAUNCH_V1_SCENARIO_IDS: frozenset[str]`
- Produces: `METRIC_NAMES: tuple[str, ...]`
- Produces: `canonical_summary_payload(summary) -> dict[str, object]`
- Preserves: `assert_product_launch_regression_gate(results: Sequence[EvaluationResult]) -> None`

- [ ] **Step 1: 写入 canonical hash RED 测试**

```python
def test_canonical_summary_hash_normalizes_semantically_unordered_lists():
    result = run_product_launch_suite()[0]
    summary = result.actual_summary
    reordered = summary.model_copy(
        update={
            "approval_reasons": list(reversed(summary.approval_reasons)),
            "errors": list(reversed(summary.errors)),
            "validation": list(reversed(summary.validation)),
            "selected_listing_versions": list(reversed(summary.selected_listing_versions)),
            "publish": list(reversed(summary.publish)),
        }
    )
    assert canonical_summary_hash(reordered) == canonical_summary_hash(summary)
```

- [ ] **Step 2: 写入 scenario/metric/hash fail-closed RED 测试**

```python
def test_product_launch_gate_rejects_empty_metrics():
    results = run_product_launch_suite()
    results[0] = results[0].model_copy(update={"metrics": []})
    with pytest.raises(EvaluationGateError, match="metric_set"):
        assert_product_launch_regression_gate(results)


def test_product_launch_gate_rejects_scenario_set_drift():
    results = run_product_launch_suite()
    with pytest.raises(EvaluationGateError, match="scenario_set"):
        assert_product_launch_regression_gate(results[:-1])


def test_product_launch_gate_recomputes_actual_hash():
    results = run_product_launch_suite()
    results[0] = results[0].model_copy(update={"actual_summary_hash": "0" * 64})
    with pytest.raises(EvaluationGateError, match="actual_summary_hash"):
        assert_product_launch_regression_gate(results)
```

- [ ] **Step 3: 运行 RED 测试**

Run: `python -m pytest tests/test_product_launch_golden.py -k "canonical or gate_rejects or recomputes" -q`

Expected: FAIL；当前门禁未拒绝空 metrics/缺失 scenario，列表重排改变 hash。

- [ ] **Step 4: 实现固定集合和规范化 payload**

```python
PRODUCT_LAUNCH_V1_SCENARIO_IDS = frozenset(
    {
        "adapter-validation-failure",
        "high-risk-supplier",
        "localization-claim",
        "low-profit",
        "missing-approval",
        "tampered-version-hash",
        "three-platform-approved-publish",
    }
)

METRIC_NAMES = (
    "identity_match",
    "state_and_risk_match",
    "approval_and_snapshot_match",
    "listing_version_match",
    "validation_match",
    "publish_match",
    "trace_match",
    "error_match",
)
```

`canonical_summary_payload()` 必须复制 JSON-mode payload，并对 reasons/errors/source IDs 按字典序排序，对 validation/version/publish 按 marketplace 和稳定 ID 排序。门禁按顺序验证 scenario 唯一且集合精确、metric 唯一且集合精确、actual hash 重算、passed 结果 expected hash 等于 actual hash、所有分数和阈值为 1。

- [ ] **Step 5: 运行 GREEN 与全量测试**

Run: `python -m pytest tests/test_product_launch_golden.py -q`

Expected: PASS。

Run: `python -m pytest -q`

Expected: PASS，数量记录到 Node 16 progress log。

- [ ] **Step 6: 本地提交，等待集成评审**

```text
git diff --check
git add backend/app/agents/evaluation/results.py backend/app/agents/evaluation/runner.py backend/tests/test_product_launch_golden.py
git commit -m "修复：收紧 Product Launch 黄金评估门禁"
```

---

### Task 2: LG17-EXEC-01 审批绑定与执行提交顺序

**Files:**
- Modify: `backend/app/tools/schemas.py`
- Modify: `backend/app/tools/executor.py`
- Modify: `backend/tests/test_tool_executor.py`

**Interfaces:**
- Produces: `ToolApprovalBinding`
- Produces: `canonical_tool_input_hash(arguments) -> str`
- Changes: `ApprovalProofVerifier.verify(*, request, tool, input_hash)`
- Produces: `ToolExecutionCommitStore.commit_success(identity, *, input_hash, result, outbox_entry) -> None`
- Produces: trace outbox delivery methods

- [ ] **Step 1: 写入审批证明 RED 测试**

先按下面的完整实现扩展现有 helper，并在测试文件增加 `hashlib/json` import。测试 helper 用普通 dict 生成未来契约，不依赖尚未实现的生产 `ToolApprovalBinding`，因此 RED 失败只来自 verifier 行为。

```python
def _approval_executor(
    repository: ApprovalRepository,
    *,
    track_calls: bool = False,
):
    executor_api = _executor_api()
    catalog_api = _catalog_api()
    tool = ToolDefinition(
        name="publish_listing",
        description="approval boundary test tool",
        risk_level=RiskLevel.HIGH,
        required_permission="listing:publish",
        requires_approval=True,
        input_model=ApprovalToolInput,
        output_model=ApprovalToolOutput,
    )
    calls: list[str] = []
    catalog = catalog_api.ToolHandlerCatalog()

    async def handler(input_data, context):
        calls.append(context.request_id)
        return ApprovalToolOutput(accepted=True)

    catalog.register("publish_listing", handler)
    executor = _executor(
        registry=ToolRegistry([tool]),
        handlers=catalog,
        approval_verifier=executor_api.RepositoryApprovalProofVerifier(repository),
    )
    return (executor, calls) if track_calls else executor


def _store_approval(
    repository: ApprovalRepository,
    *,
    status: ApprovalStatus = ApprovalStatus.APPROVED,
    tenant_id: str = "tenant-a",
    workflow_id: str = "wf-1",
    tool_name: str = "publish_listing",
    idempotency_key: str | None = None,
    binding_overrides: dict[str, object] | None = None,
) -> str:
    canonical = json.dumps(
        {"value": "payload"}, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    binding = {
        "schema_version": "tool-approval-binding/v1",
        "tenant_id": tenant_id,
        "workflow_id": workflow_id,
        "actor_id": "actor-1",
        "tool_name": tool_name,
        "tool_version": "1.0.0",
        "input_hash": hashlib.sha256(canonical).hexdigest(),
        "idempotency_key": idempotency_key,
    }
    binding.update(binding_overrides or {})
    approval_id = "approval-1"
    metadata = {"tool": tool_name, "tool_approval_binding": binding}
    if idempotency_key is not None:
        metadata["idempotency_key"] = idempotency_key
    repository.upsert_pending(
        approval_id=approval_id,
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        requested_by="actor-1",
        reason_codes=["high_risk_tool"],
        risk_level=RiskLevel.HIGH,
        resource_type="tool_call",
        resource_id="req-publish_listing",
        metadata=metadata,
    )
    if status == ApprovalStatus.APPROVED:
        repository.approve(approval_id, reviewer_id="reviewer-1")
    elif status == ApprovalStatus.REJECTED:
        repository.reject(approval_id, reviewer_id="reviewer-1")
    return approval_id


@pytest.mark.parametrize("field", ["actor_id", "tool_version", "input_hash"])
def test_approval_proof_binds_actor_version_and_input_hash(field):
    repository = ApprovalRepository()
    executor, handler_calls = _approval_executor(repository, track_calls=True)
    approval_id = _store_approval(
        repository,
        binding_overrides={field: "tampered"},
    )
    request = _request(
        "publish_listing",
        {"value": "payload"},
        agent_role=AgentRole.SUPERVISOR,
        approval_id=approval_id,
    )
    result = asyncio.run(executor.execute(request))
    assert result.ok is False
    assert result.code == "approval_invalid"
    assert handler_calls == []
```

- [ ] **Step 2: 写入 trace 失败不重放 RED 测试**

在测试文件增加 `from app.agents.observability.schema import TraceEvent`，并定义兼容旧 `get/save` 与新 `commit_success` 协议的测试 store；它不是生产 factory，旧 executor 仍可运行到 trace-before-save 的真实失败点。

```python
class AlwaysFailTraceRepository:
    def record(self, event: TraceEvent) -> None:
        raise RuntimeError("synthetic trace outage")


def _commit_store():
    executor_api = _executor_api()

    class RecordingCommitStore(executor_api.InMemoryIdempotencyStore):
        def __init__(self) -> None:
            super().__init__()
            self._pending = {}

        def commit_success(
            self, identity, *, input_hash, result, outbox_entry
        ) -> None:
            self.save(identity, input_hash, result)
            self._pending[outbox_entry.outbox_id] = outbox_entry

        def pending_trace_events(self):
            return tuple(self._pending.values())

        def mark_trace_delivered(self, outbox_id: str) -> None:
            self._pending.pop(outbox_id, None)

    return RecordingCommitStore()


def test_trace_failure_does_not_replay_committed_side_effect():
    calls = []

    async def handler(input_data, context):
        calls.append(input_data.value)
        return RuntimeToolOutput(accepted=True)

    commit_store = _commit_store()
    executor = _runtime_executor(
        handler,
        idempotent=True,
        idempotency_store=commit_store,
        trace_repository=AlwaysFailTraceRepository(),
    )
    request = _runtime_request(idempotency_key="stable-key")
    first = asyncio.run(executor.execute(request))
    second = asyncio.run(executor.execute(request))
    assert first.ok is True
    assert second.ok is True and second.replayed is True
    assert len(calls) == 1
    assert len(commit_store.pending_trace_events()) == 1
```

- [ ] **Step 3: 运行 RED 测试**

Run: `python -m pytest tests/test_tool_executor.py -k "approval_proof_binds or trace_failure_does_not_replay" -q`

Expected: FAIL；当前 verifier 未绑定完整证明，trace 异常会在结果缓存前逃逸。

- [ ] **Step 4: 增加严格审批绑定模型**

```python
class ToolApprovalBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    schema_version: Literal["tool-approval-binding/v1"]
    tenant_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    tool_version: str = Field(min_length=1)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    idempotency_key: str | None = None
```

Executor 必须先验证 input model 并通过公开 `canonical_tool_input_hash(arguments) -> str` 计算完整 canonical input hash，再调用 verifier。Verifier 从 approval metadata 严格解析 `ToolApprovalBinding`，不接受缺字段或额外字段。生产 canonical 函数与测试 helper 对 JSON-mode dict 使用 UTF-8、sorted keys 和紧凑 separators；测试另加 Unicode、嵌套 dict/list 和字段顺序用例，防止两套摘要漂移。

- [ ] **Step 5: 增加结果与 outbox 原子提交协议**

```python
class ToolTraceOutboxEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    outbox_id: str
    event: TraceEvent
    delivered: bool = False


class ToolExecutionCommitStore(Protocol):
    def commit_success(
        self,
        identity: tuple[str, str, str, str],
        *,
        input_hash: str,
        result: ToolResult,
        outbox_entry: ToolTraceOutboxEntry,
    ) -> None:
        raise NotImplementedError

    def pending_trace_events(self) -> tuple[ToolTraceOutboxEntry, ...]:
        raise NotImplementedError

    def mark_trace_delivered(self, outbox_id: str) -> None:
        raise NotImplementedError
```

`outbox_id` 使用 request_id、tool version、attempt 和 status 的稳定 SHA-256，不依赖后续 Trace v2 的 event_id。Handler 成功后先在 store 同一锁内提交 result 与 outbox entry，再尝试写 TraceRepository；trace 异常保留 pending entry，但返回已提交 ToolResult。重复请求直接回放结果，不重新调用 handler。

- [ ] **Step 6: 运行 GREEN 与回归测试**

Run: `python -m pytest tests/test_tool_executor.py -q`

Run: `python -m pytest -q`

Expected: 均 PASS。

- [ ] **Step 7: 分两个中文提交，等待集成评审**

```text
git diff --check
git commit -m "修复：绑定工具审批证明与规范化输入"
git commit -m "修复：先提交幂等结果与追踪发件箱"
```

---

### Task 3: LG18-OPS-01 订单生命周期与币种汇总

**Files:**
- Modify: `backend/app/domain/operations.py`
- Modify: `backend/app/services/operations.py`
- Modify: `backend/app/mock_data/operations/inventory.json`
- Modify: `backend/app/mock_data/operations/metrics.json`
- Modify: `backend/app/mock_data/operations/orders.json`
- Modify: `backend/app/mock_data/operations/shipments.json`
- Modify: `backend/tests/test_operations_agent.py`
- Modify: `docs/progress/2026-07-13-node-18-operations-agent.md`

**Interfaces:**
- Changes: `OperationsEvent.observed_at` to `occurred_at`
- Produces: `IdentityString`, `CurrencyCode`
- Changes: `OpsPerformanceSummary.gross_revenue_by_currency`
- Produces: `_latest_order_events(records) -> dict[str, OrderEvent]`

- [ ] **Step 1: 写入订单最终状态与币种 RED 测试**

```python
def test_summary_counts_only_latest_paid_or_fulfilled_orders():
    records = [
        _order_event(event_id="paid", order_id="o-paid", status="paid"),
        _order_event(event_id="cancelled", order_id="o-cancelled", status="cancelled"),
        _order_event(event_id="refunded", order_id="o-refunded", status="refunded"),
    ]
    summary = summarize_operations(
        OperationsReadModel(
            tenant_id="tenant-a",
            as_of=AS_OF,
            records=records,
            fresh_records=records,
        )
    )[0]
    assert summary.order_count == 1
    assert summary.units_sold == 1


def test_summary_partitions_revenue_by_currency():
    records = [
        _order_event(event_id="usd", order_id="usd", currency="USD", gross_revenue="10"),
        _order_event(event_id="eur", order_id="eur", currency="EUR", gross_revenue="20"),
    ]
    summary = summarize_operations(
        OperationsReadModel(
            tenant_id="tenant-a",
            as_of=AS_OF,
            records=records,
            fresh_records=records,
        )
    )[0]
    assert summary.gross_revenue_by_currency == {
        "EUR": Decimal("20"),
        "USD": Decimal("10"),
    }
```

- [ ] **Step 2: 写入时序和空白 identity RED 测试**

`test_summary_selects_latest_order_by_occurred_received_event_id` 分别制造 occurred_at、received_at、event_id 平局；`test_operations_identity_fields_reject_whitespace` 参数化 tenant/listing/version/sku/order/shipment/event 字段并期望 `ValidationError`。

- [ ] **Step 3: 运行 RED 和格式门禁**

Run: `python -m pytest tests/test_operations_agent.py -k "latest_order or partitions_revenue or whitespace" -q`

Expected: FAIL。

Run from repository root: `git diff --check 106544d7d7dd8585da387c946375ef2f0ad44200..HEAD`

Expected: FAIL，指出 progress log 第 3、4 行尾随空格。

- [ ] **Step 4: 实现稳定时序与收入分区**

```python
IdentityString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
CurrencyCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]


def _latest_order_events(records: Iterable[OrderEvent]) -> dict[str, OrderEvent]:
    latest: dict[str, OrderEvent] = {}
    for record in records:
        current = latest.get(record.order_id)
        key = (record.occurred_at, record.received_at, record.event_id)
        if current is None or key > (
            current.occurred_at,
            current.received_at,
            current.event_id,
        ):
            latest[record.order_id] = record
    return latest
```

只保留最终状态 `paid`、`fulfilled` 进入 order_count、units 和 revenue；pending/cancelled/returned/refunded 排除。收入按 currency 分区并稳定排序。同步迁移 JSON fixture 和 helper。

- [ ] **Step 5: 运行 GREEN、全量与格式检查**

Run: `python -m pytest tests/test_operations_agent.py -q`

Run: `python -m pytest -q`

Run from repository root: `git diff --check 106544d7d7dd8585da387c946375ef2f0ad44200..HEAD`

Expected: 均 PASS。

- [ ] **Step 6: 本地提交，等待集成评审**

```text
git commit -m "修复：按订单最终状态和币种汇总运营收入"
git commit -m "文档：清理运营 Agent 进展记录格式"
```

---

### Task 4: LG19-RAG-01 实体引用与评估门禁

**Files:**
- Modify: `backend/app/domain/support.py`
- Modify: `backend/app/rag/support/planner.py`
- Modify: `backend/app/rag/support/evaluation.py`
- Modify: `backend/tests/test_support_rag.py`

**Interfaces:**
- Produces: `EntityReferences`
- Changes: `SupportRequest.entity_refs`
- Changes: `PlannerDecision.route` adds `clarification`
- Produces: `assert_support_evaluation_gate(cases, report)`

- [ ] **Step 1: 写入实体引用 RED 测试**

```python
def test_planner_requires_validated_entity_refs_instead_of_query_text():
    request = support_request(query="order A-100 status", entity_refs=EntityReferences())
    decision = RuleBasedSupportPlanner().plan(request)
    assert decision.route == "clarification"
    assert decision.transaction_request is None
    assert decision.clarification_fields == ("order_id",)
```

参数化七工具实体矩阵，证明 OR 条件和 clarification 字段精确，工具参数只来自 `entity_refs`。

- [ ] **Step 2: 写入十类评估 fail-closed RED 测试**

```python
def test_support_gate_rejects_zero_denominator(service):
    cases = load_support_evaluation_cases()
    report = evaluate_support_rag(service, cases).model_copy(
        update={"permission_case_count": 0}
    )
    with pytest.raises(SupportEvaluationGateError, match="denominator"):
        assert_support_evaluation_gate(cases, report)
```

同时覆盖空 cases、缺失/多余/重复 category、failed IDs、模型调用非零、provider cost 非零、p95 超过 2000ms。

- [ ] **Step 3: 运行 RED**

Run: `python -m pytest tests/test_support_rag.py -k "entity_refs or clarification or evaluation_gate" -q`

Expected: FAIL。

- [ ] **Step 4: 实现 EntityReferences 与 Planner 路由**

```python
class EntityReferences(SupportContract):
    order_id: str | None = Field(default=None, min_length=1, max_length=128)
    shipment_id: str | None = Field(default=None, min_length=1, max_length=128)
    payment_id: str | None = Field(default=None, min_length=1, max_length=128)
    refund_id: str | None = Field(default=None, min_length=1, max_length=128)
    sku: str | None = Field(default=None, min_length=1, max_length=128)
    coupon_code: str | None = Field(default=None, min_length=1, max_length=128)
    customer_id: str | None = Field(default=None, min_length=1, max_length=128)
```

Planner 只识别 intent，禁止从 query 抽取 ID；交易 intent 缺字段时 route=`clarification`，不产生 transaction request。

- [ ] **Step 5: 实现评估报告分母与 gate**

Report 增加 `category_counts`、四项 denominator、`model_call_count`、`provider_cost_usd`、`p95_latency_ms`。Gate 要求十类集合精确且每类大于 0，所有 denominator 大于 0，并执行规范阈值。

- [ ] **Step 6: 运行 GREEN 与全量测试**

Run: `python -m pytest tests/test_support_rag.py -q`

Run: `python -m pytest -q`

Expected: 均 PASS。

- [ ] **Step 7: 提交独立修复**

```text
git diff --check
git commit -m "修复：要求客服交易工具使用可信实体引用"
git commit -m "修复：收紧客服 RAG 十类评估门禁"
```

---

### Task 5: Node 19 同步 Node 17 并统一七工具

**Files:**
- Modify: `backend/app/tools/registry.py`
- Create: `backend/app/tools/catalog/support.py`
- Modify: `backend/app/tools/catalog/deterministic.py`
- Modify: `backend/app/tools/catalog/__init__.py`
- Create: `backend/app/adapters/support_transactions.py`
- Create: `backend/app/mock_data/support_transactions/__init__.py`
- Create: `backend/app/mock_data/support_transactions/v1.json`
- Modify: `backend/app/agents/profiles.py`
- Modify: `backend/app/domain/support.py`
- Modify: `backend/tests/test_support_rag.py`
- Modify: `backend/tests/test_tool_executor.py`

**Interfaces:**
- Produces: `build_support_tool_definitions()`
- Produces: `register_support_handlers(catalog)`
- Consumes: Node 17 typed ToolDefinition, ToolHandlerCatalog, ToolExecutor

- [ ] **Step 1: 合并修复后的 Node 17**

Run in Node 19 worktree: `git merge --no-ff codex/node-17-tool-executor -m "合并：同步 Node 17 工具执行契约"`

Expected: merge succeeds；如 registry/catalog 冲突，在 Node 19 中按修复后的 Node 17 契约解决，不回退 Node 17 行为。

- [ ] **Step 2: 写入工具矩阵 RED 测试**

```python
def test_support_tools_align_registry_profile_schema_and_handlers():
    expected = {
        "get_order_status",
        "get_shipment_trajectory",
        "get_payment_status",
        "get_refund_amount",
        "get_inventory_status",
        "get_coupon_status",
        "get_ticket_history",
    }
    registry = build_default_registry()
    catalog = build_default_handler_catalog()
    profile = get_agent_profile(AgentRole.CUSTOMER_SUPPORT)
    assert expected <= registry.names()
    assert expected <= catalog.names()
    assert expected <= profile.allowed_tools
    assert all(registry.get(name).input_model for name in expected)
    assert all(registry.get(name).output_model for name in expected)
```

- [ ] **Step 3: 运行 RED**

Run: `python -m pytest tests/test_tool_executor.py tests/test_support_rag.py -k "support_tools_align or transaction_tool_entity" -q`

Expected: FAIL，七工具尚未注册或没有 handler/schema。

- [ ] **Step 4: 实现单一工具矩阵真源**

七个 definition 使用严格独立输入输出 model，统一权限 `support:transaction:read`、RiskLevel.LOW、无需审批、只读 retry policy。`InMemorySupportTransactionAdapter` 从版本化 fixture 读取按 tenant 分区的演示事实；Handler 从 `ToolExecutionContext.tenant_id` 读取租户并调用 adapter，禁止使用请求参数覆盖 tenant。

- [ ] **Step 5: 运行 GREEN、全量、格式检查并提交**

Run: `python -m pytest tests/test_tool_executor.py tests/test_support_rag.py -q`

Run: `python -m pytest -q`

Run from root: `git diff --check`

```text
git commit -m "修复：统一客服交易工具注册与处理器契约"
```

---

### Task 6: 独立评审与集成分支

**Files:**
- Create: `docs/progress/2026-07-14-langgraph-standard-runtime-integration.md`

- [ ] **Step 1: 为四个修复分支分别启动独立 reviewer**

Reviewer 读取设计规范、对应 issue、分支 diff 和聚焦测试结果。Critical/Important 必须回源分支修复；不得在集成分支掩盖。

- [ ] **Step 2: 锁定 dev-com 集成基线**

```text
$planBase = git log -1 --format=%H -- docs/superpowers/plans/2026-07-13-node-16-19-hardening-integration.md
git branch --show-current
git merge-base --is-ancestor $planBase dev-com
git status --short
```

当前分支必须输出 `dev-com`，祖先检查必须 exit 0。状态只允许出现三份已知用户文档；合并和提交始终使用精确 pathspec，禁止暂存它们。

- [ ] **Step 3: 依序合并和验证**

```text
git merge --no-ff codex/node-16-product-launch-golden-evals -m "合并：集成 Product Launch 黄金评估"
python -m pytest tests/test_product_launch_golden.py -q
python -m pytest -q
git diff --check $planBase..HEAD
$node16Merge = git rev-parse HEAD

git merge --no-ff codex/node-17-tool-executor -m "合并：集成统一工具执行器"
git merge-base --is-ancestor $node16Merge HEAD
python -m pytest tests/test_tool_executor.py -q
python -m pytest -q
git diff --check $node16Merge..HEAD
$node17Merge = git rev-parse HEAD

git merge --no-ff codex/node-18-operations-agent -m "合并：集成运营 Agent"
git merge-base --is-ancestor $node17Merge HEAD
python -m pytest tests/test_operations_agent.py -q
python -m pytest -q
git diff --check $node17Merge..HEAD
$node18Merge = git rev-parse HEAD

git merge --no-ff codex/node-19-support-rag -m "合并：集成客服 Routed RAG"
git merge-base --is-ancestor $node18Merge HEAD
python -m pytest tests/test_support_rag.py tests/test_tool_executor.py -q
python -m pytest -q
git diff --check $node18Merge..HEAD
$node19Merge = git rev-parse HEAD
```

每个阶段同时从仓库根执行 `git diff --check`。Node 19 已包含 Node 17 历史时，最后一次 merge 只能引入 Node 19 增量。

- [ ] **Step 4: 记录集成基线并推送**

更新中文 progress log，记录四个最终 HEAD、四个 merge SHA、每次聚焦/全量测试真实数量和 reviewer 结论；追加唯一一行 `NODE_INTEGRATION_SHA=` 与 `$node19Merge` 的 40 位小写值。后续目录迁移按其 Global Constraints 中的固定 PowerShell 门禁读取。

```text
git push -u origin dev-com
```
