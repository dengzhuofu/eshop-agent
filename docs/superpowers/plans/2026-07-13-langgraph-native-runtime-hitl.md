# LangGraph 原生 Runtime 与 HITL 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Product Launch 从手工 snapshot 加第二张 publish graph 迁移为稳定 thread_id、原生 checkpointer、`interrupt()` 和 `Command(resume=...)` 的单图 HITL，并建立审批、发布账本、trace 和版本兼容边界。

**Architecture:** `ApplicationContainer` 持有单例 saver/store 和业务仓储；GraphRuntimeContext 传递请求身份，依赖在构图时注入。WorkflowExecution 保存公开 workflow 与内部 thread 绑定；Approval 保存授权事实并绑定精确 checkpoint/interrupt；PublishOperation 保存外部副作用结果和 outbox。

**Tech Stack:** Python 3.12, LangGraph 1.2.9, Pydantic 2.11.7, FastAPI, pytest.

## Global Constraints

- 前置分支必须完成 `backend/src/app` 标准迁移、三图 manifest 和隔离 ApplicationContainer。
- MVP profile 仅承诺单进程单 worker；跨进程 durable 与 fencing 的真实持久化验证标记为 PostgreSQL integration profile。
- `workflow_id`、`thread_id`、`run_id` 分别为 `wf_`、`th_`、`run_` 加 UUIDv4；公开 DTO 禁止输出 thread/checkpoint/interrupt ID。
- API 认证上下文是 tenant、subject、permission 的唯一真源；state 和请求 body 不能授予权限。
- Checkpointer 不代替 Approval、Trace 或 PublishOperation；pending writes 不代表外部 exactly-once。
- 保留 listing version hash、批准版本完整集合和多平台部分成功语义。
- 开始本计划前，从 progress log 唯一提取 `LAYOUT_FINAL_SHA`，校验格式、Git 对象和祖先关系；使用下方命令，任一步非零立即停止。
- 本计划提交最终合入并推送 `dev-com`，禁止合并或推送 `main`。
- 每个任务 RED/GREEN、聚焦/全量验证、独立提交；复杂恢复和副作用代码使用必要中文注释。

```powershell
$progressPath = "docs/progress/2026-07-14-langgraph-standard-runtime-integration.md"
$shaLines = @(Get-Content -Encoding UTF8 $progressPath | Where-Object {
    $_ -match '^LAYOUT_FINAL_SHA=[0-9a-f]{40}$'
})
if ($shaLines.Count -ne 1) { throw "LAYOUT_FINAL_SHA must appear exactly once" }
$layoutFinalSha = $shaLines[0].Split('=', 2)[1]
git cat-file -e ($layoutFinalSha + "^{commit}")
if ($LASTEXITCODE -ne 0) { throw "LAYOUT_FINAL_SHA is not a commit" }
git merge-base --is-ancestor $layoutFinalSha HEAD
if ($LASTEXITCODE -ne 0) { throw "LAYOUT_FINAL_SHA is not an ancestor" }
```

---

### Task 1: WorkflowExecution、Run Claim 与启动幂等

**Files:**
- Create: `backend/src/app/domain/workflows.py`
- Create: `backend/src/app/persistence/repositories/workflow_executions.py`
- Create: `backend/src/app/services/canonicalization.py`
- Modify: `backend/src/app/runtime/container.py`
- Create: `backend/tests/unit/runtime/test_workflow_executions.py`

**Interfaces:**
- Produces: `WorkflowExecution`
- Produces: `WorkflowExecutionRepository.create_or_get(command, *, tenant_id, subject_id, idempotency_key) -> WorkflowRegistration`
- Produces: `claim_run(execution, *, operation, expected_version, lease_seconds) -> RunClaim`
- Produces: `record_pause_reference(...) -> WorkflowExecution` and `complete_run(...) -> WorkflowExecution`
- Produces: request and idempotency digests

- [ ] **Step 1: 写入 ID 与幂等 RED 测试**

```python
def test_start_without_key_allocates_new_workflow_and_thread(repository, command):
    first = repository.create_or_get(
        command, tenant_id="tenant-a", subject_id="subject-a", idempotency_key=None
    )
    second = repository.create_or_get(
        command, tenant_id="tenant-a", subject_id="subject-a", idempotency_key=None
    )
    assert first.execution.workflow_id != second.execution.workflow_id
    assert first.execution.thread_id != second.execution.thread_id


def test_same_key_with_different_digest_conflicts(repository, command):
    repository.create_or_get(
        command, tenant_id="tenant-a", subject_id="subject-a", idempotency_key="client-1"
    )
    with pytest.raises(IdempotencyConflictError, match="idempotency_conflict"):
        repository.create_or_get(
            command.model_copy(update={"target_price": 99}),
            tenant_id="tenant-a",
            subject_id="subject-a",
            idempotency_key="client-1",
        )


def test_active_resume_lease_rejects_second_claim(repository, awaiting_execution):
    first = repository.claim_run(
        awaiting_execution,
        operation="resume",
        expected_version=awaiting_execution.record_version,
        lease_seconds=30,
    )
    current = repository.require_for_tenant(
        awaiting_execution.workflow_id, tenant_id=awaiting_execution.tenant_id
    )
    second = repository.claim_run(
        current,
        operation="resume",
        expected_version=current.record_version,
        lease_seconds=30,
    )
    assert first.claimed is True
    assert second.claimed is False
    assert second.reason == "run_in_progress"


def test_stale_fencing_token_cannot_complete_newer_run(repository, expired_claim):
    reclaimed = repository.claim_run(
        expired_claim.execution,
        operation="resume",
        expected_version=expired_claim.execution.record_version,
        lease_seconds=30,
    )
    with pytest.raises(StaleRunError, match="run_fenced"):
        repository.complete_run(
            reclaimed.execution,
            run_id=expired_claim.run_id,
            fencing_token=expired_claim.fencing_token,
            status="completed",
            expected_version=reclaimed.execution.record_version,
        )
```

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/unit/runtime/test_workflow_executions.py -q`

Expected: FAIL，模型和仓储不存在。

- [ ] **Step 3: 实现冻结模型**

```python
class WorkflowExecution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    workflow_id: str
    tenant_id: str
    graph_id: Literal["product_launch", "operations", "support"]
    thread_id: str
    requested_by_subject: str
    runtime_mode: Literal["native_v1"] = "native_v1"
    status: ExecutionStatus
    graph_revision: str
    state_schema_version: int = Field(ge=1)
    request_digest: str
    idempotency_key_digest: str | None
    approval_id: str | None = None
    checkpoint_id: str | None = None
    interrupt_id: str | None = None
    active_run_id: str | None = None
    run_ids: tuple[str, ...]
    run_fencing_token: int = Field(ge=0)
    lease_expires_at: datetime | None = None
    record_version: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime


class WorkflowRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution: WorkflowExecution
    created: bool


class RunClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    execution: WorkflowExecution
    run_id: str
    fencing_token: int
    claimed: bool
    reason: Literal[
        "claimed", "terminal", "run_in_progress", "not_startable", "not_resumable"
    ]
```

仓储在同一锁内维护 `(tenant_id, graph_id, idempotency_key_digest)` 唯一索引；同 key 同 digest 返回 `created=False` 的已有 execution，同 key 异 digest 冲突，无 key 永远新建。`claim_run()` 为每次 start/resume/no-op 请求生成新的 run_id 并追加 `run_ids`：start 从 created claim，resume 从 awaiting_approval claim或从 lease 已过期的 running 状态重新 claim；终态返回 `reason="terminal"`，有效 lease 下的 running 返回 `run_in_progress`，过期 lease 递增 fencing token。`record_pause_reference()` 和 `complete_run()` 必须同时匹配 tenant、run_id、fencing token、expected record_version；旧 worker 永远不能覆盖新 run。所有 get/update API 强制 tenant scope。

同一提交修改 `ApplicationContainer`，新增必填 `workflow_executions: WorkflowExecutionRepository`，并在 `create_application_container()` 中创建实例；workflow service 禁止自行构造仓储。

- [ ] **Step 4: 运行 GREEN、全量并提交**

Run: `python -m pytest tests/unit/runtime/test_workflow_executions.py -q`

Run: `python -m pytest -q`

```text
git diff --check
git commit -m "功能：增加工作流执行与启动幂等账本"
```

---

### Task 2: 审批契约与原生单图中断骨架

**Files:**
- Modify: `backend/src/app/domain/approvals.py`
- Create: `backend/src/app/runtime/interrupts.py`
- Modify: `backend/src/app/workflows/product_launch/state.py`
- Modify: `backend/src/app/workflows/product_launch/graph.py`
- Modify: `backend/src/app/workflows/product_launch/edges.py`
- Modify: `backend/src/app/workflows/product_launch/nodes/approval.py`
- Create: `backend/tests/unit/runtime/test_approval_interrupts.py`
- Create: `backend/tests/integration/workflows/test_native_product_launch_runtime.py`

**Interfaces:**
- Produces: `ApprovalIntent`, `ApprovalInterrupt`, `ApprovalDecision`
- Produces: `digest_approval_intent(intent) -> str`
- Produces: `approval_gate_node` using `interrupt()`
- Produces: `route_after_approval`
- Preserves: all pre-publish deterministic nodes

- [ ] **Step 1: 写入审批契约和原生 interrupt RED 测试**

```python
def test_intent_digest_changes_when_tool_version_changes(intent):
    changed = intent.model_copy(update={"tool_version": "2.0.0"})
    assert digest_approval_intent(changed) != digest_approval_intent(intent)


def test_product_launch_pauses_with_native_interrupt(container, graph, state, context):
    config = {"configurable": {"thread_id": "th_test"}}
    result = graph.invoke(state, config=config, context=context)
    snapshot = graph.get_state(config)
    assert result["__interrupt__"]
    assert snapshot.next == ("approval_gate",)
    assert snapshot.interrupts[0].id
    assert snapshot.config["configurable"]["checkpoint_id"]
```

另加 `test_rebuilt_graph_resumes_with_same_saver` 和 `test_runtime_identity_is_not_checkpoint_state`。

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/unit/runtime/test_approval_interrupts.py tests/integration/workflows/test_native_product_launch_runtime.py -q`

Expected: FAIL，当前仍在 await_approval 后结束并依赖第二张图。

- [ ] **Step 3: 实现严格审批模型、摘要和 approval gate**

```python
class ApprovalIntent(StrictApprovalModel):
    schema_version: Literal["approval-intent/v1"]
    approval_id: str
    tenant_id: str
    workflow_id: str
    graph_id: Literal["product_launch"]
    tool_name: str
    tool_version: str
    actor_id: str
    listing_version_ids: tuple[str, ...]
    marketplaces: tuple[Marketplace, ...]
    canonical_input_hash: str


class ApprovalInterrupt(StrictApprovalModel):
    schema_version: Literal["approval-interrupt/v1"]
    approval_id: str
    intent_digest: str
    reason_codes: tuple[str, ...]
    risk_level: RiskLevel
    expires_at: datetime


class ApprovalDecision(StrictApprovalModel):
    schema_version: Literal["approval-decision/v1"]
    approval_id: str
    status: Literal["approved", "rejected", "expired", "revoked"]
    intent_digest: str
    reviewer_subject: str
    decision_version: int
    decided_at: datetime


def digest_approval_intent(intent: ApprovalIntent) -> str:
    payload = json.dumps(
        intent.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def approval_gate_node(state: ProductLaunchState) -> dict:
    payload = ApprovalInterrupt.model_validate(state["approval_interrupt"])
    decision = ApprovalDecision.model_validate(interrupt(payload.model_dump(mode="json")))
    return {"approval_decision": decision.model_dump(mode="json")}
```

Graph 在 risk 后进入 ensure_approval、approval_gate、route_after_approval；approved 进入 verify/publish，rejected 进入 reject_complete，expired/revoked 进入 approval_invalid。`edges.py` 只读 state 并返回 Literal route。

- [ ] **Step 4: 运行 GREEN 与 Product 回归**

Run: `python -m pytest tests/unit/runtime/test_approval_interrupts.py tests/integration/workflows/test_native_product_launch_runtime.py tests/integration/workflows/test_product_launch_graph.py -q`

Expected: PASS。

- [ ] **Step 5: 提交**

```text
git diff --check
git commit -m "功能：定义审批契约并迁移商品发布原生 HITL"
```

---

### Task 3: 审批 Checkpoint CAS 与 Reconciliation

**Files:**
- Modify: `backend/src/app/domain/approvals.py`
- Modify: `backend/src/app/persistence/repositories/approvals.py`
- Create: `backend/src/app/persistence/runtime_uow.py`
- Modify: `backend/src/app/runtime/container.py`
- Modify: `backend/src/app/workflows/product_launch/nodes/approval.py`
- Modify: `backend/tests/unit/runtime/test_approval_interrupts.py`
- Modify: `backend/tests/integration/persistence/test_approval_repository.py`
- Create: `backend/tests/integration/persistence/test_runtime_uow.py`

**Interfaces:**
- Consumes: strict approval models and digest from Task 2
- Produces: `upsert_pending`, `bind_interrupt`, `decide`
- Produces: `RuntimeUnitOfWork.record_pause(...) -> WorkflowExecution`

- [ ] **Step 1: 写入 CAS 与 reconciliation RED 测试**

```python
def test_same_approval_id_with_different_digest_conflicts(repository, intent):
    repository.upsert_pending(intent)
    with pytest.raises(ApprovalConflictError, match="intent_digest"):
        repository.upsert_pending(intent.model_copy(update={"tool_version": "2"}))


def test_interrupt_binding_rejects_different_checkpoint(repository, intent):
    approval = repository.upsert_pending(intent)
    repository.bind_interrupt(
        approval.id,
        tenant_id=intent.tenant_id,
        checkpoint_id="cp-1",
        interrupt_id="int-1",
        expected_digest=digest_approval_intent(intent),
        expected_version=approval.record_version,
    )
    with pytest.raises(ApprovalConflictError, match="checkpoint"):
        repository.bind_interrupt(
            approval.id,
            tenant_id=intent.tenant_id,
            checkpoint_id="cp-2",
            interrupt_id="int-1",
            expected_digest=digest_approval_intent(intent),
            expected_version=approval.record_version + 1,
        )


def test_record_pause_rolls_back_execution_and_approval_together(
    runtime_uow, executions, approvals, running_execution, pending_approval
):
    runtime_uow.fail_after_approval_binding = True
    with pytest.raises(RuntimeError, match="synthetic_uow_failure"):
        runtime_uow.record_pause(
            execution=running_execution,
            approval_id=pending_approval.id,
            checkpoint_id="cp-1",
            interrupt_id="int-1",
            run_id=running_execution.active_run_id,
            fencing_token=running_execution.run_fencing_token,
            expected_execution_version=running_execution.record_version,
            expected_approval_version=pending_approval.record_version,
        )
    current_execution = executions.require_for_tenant(
        running_execution.workflow_id, tenant_id=running_execution.tenant_id
    )
    current_approval = approvals.get(pending_approval.id)
    assert current_execution.status == "running"
    assert current_approval.checkpoint_id is None
```

增加 exact checkpoint/interrupt 幂等绑定、错误 ID 冲突、未绑定不得 decide、decision version CAS 和 tenant mismatch 测试。

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/unit/runtime/test_approval_interrupts.py tests/integration/persistence/test_approval_repository.py tests/integration/persistence/test_runtime_uow.py -q`

Expected: FAIL；旧 upsert 会静默返回旧记录。

- [ ] **Step 3: 实现 tenant-scoped CAS 仓储**

`upsert_pending()` 只有 approval ID 和 digest 都相同才幂等；`bind_interrupt()` 只有 pending、digest 相同且 expected_version 匹配时可写精确 IDs；相同 IDs 重放幂等，不同 IDs 冲突。`decide()` 要求 checkpoint 已绑定、decision version CAS 和 reviewer 来自 RequestContext。

`RuntimeUnitOfWork.record_pause()` 在一个事务边界内调用 Approval binding 和 `WorkflowExecutionRepository.record_pause_reference()`：同时写入 approval/checkpoint/interrupt、execution status=`awaiting_approval`、清空 lease，并校验 run_id/fencing token/两个 record version。memory profile 让 ApprovalRepository 与 WorkflowExecutionRepository 使用同一 `RLock` 和可回滚快照；PostgreSQL profile 使用同一数据库事务。任一写失败两边都回滚。

- [ ] **Step 4: 实现中断后 reconciliation**

Runner 在 invoke 暂停后读取 `graph.get_state(config)`，提取 checkpoint/interrupt ID 并通过 `RuntimeUnitOfWork.record_pause()` 绑定。LangGraph checkpoint 是事务外事实：若 checkpoint 已落但 UOW 提交失败，`get_view` 和 decision endpoint 先运行幂等 reconciliation；reconciliation 仍必须携带原 run_id/fencing token，已被新 run fencing 时只报告冲突，不覆盖新 execution。

- [ ] **Step 5: 运行 GREEN、全量并提交**

Run: `python -m pytest tests/unit/runtime/test_approval_interrupts.py tests/integration/persistence/test_approval_repository.py tests/integration/persistence/test_runtime_uow.py -q`

Run: `python -m pytest -q`

```text
git diff --check
git commit -m "功能：将审批决定绑定原生 checkpoint"
```

---

### Task 4: ProductLaunchWorkflowService 与 API 兼容

**Files:**
- Create: `backend/src/app/runtime/workflows.py`
- Modify: `backend/src/app/schemas/api.py`
- Modify: `backend/src/app/api/dependencies.py`
- Modify: `backend/src/app/api/routes/workflows.py`
- Modify: `backend/src/app/api/routes/approvals.py`
- Modify: `backend/src/app/persistence/repositories/semantic_checkpoints.py`
- Create: `backend/tests/e2e/test_product_launch_hitl.py`

**Interfaces:**
- Produces: `ProductLaunchWorkflowService.start/resume/get_view`
- Preserves: documented public route paths and response fields

- [ ] **Step 1: 写入 start/resume API RED 测试**

```python
def test_public_workflow_dtos_never_expose_thread_id(client):
    response = client.post("/workflows", json=workflow_payload())
    assert response.status_code == 200
    assert "thread_id" not in response.json()


def test_reviewer_identity_comes_from_request_context(client, pending_approval):
    response = client.post(
        f"/approvals/{pending_approval.id}/approve",
        headers={"X-Demo-Subject": "reviewer-1"},
        json={"comment": "approved"},
    )
    assert response.json()["reviewed_by"] == "reviewer-1"


def test_duplicate_start_returns_view_without_second_graph_invoke(client, graph_spy):
    headers = {"Idempotency-Key": "stable-create"}
    first = client.post("/workflows", headers=headers, json=workflow_payload())
    second = client.post("/workflows", headers=headers, json=workflow_payload())
    assert second.json()["workflow_id"] == first.json()["workflow_id"]
    assert graph_spy.invoke_count == 1


def test_terminal_resume_does_not_invoke_graph(client, completed_workflow, graph_spy):
    response = client.post(
        f"/workflows/{completed_workflow.id}/resume",
        json={"approval_request_id": completed_workflow.approval_id},
    )
    assert response.json()["state"] == "completed"
    assert graph_spy.invoke_count == 0


def test_second_resume_is_rejected_while_run_lease_is_active(
    client, awaiting_workflow, execution_repository, graph_spy
):
    execution_repository.claim_run(
        awaiting_workflow,
        operation="resume",
        expected_version=awaiting_workflow.record_version,
        lease_seconds=30,
    )
    response = client.post(
        f"/workflows/{awaiting_workflow.workflow_id}/resume",
        json={"approval_request_id": awaiting_workflow.approval_id},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "run_in_progress"
    assert graph_spy.invoke_count == 0
```

增加 create/resume legacy 字段集合、semantic snapshot 投影、重复 resume 终态、waiting 409、rejected/expired 不发布、pause 后相同 request 重试返回当前视图、lease 过期重取后旧 run completion 被 fencing、ainvoke 异常写 failed、取消写 cancelled 测试。

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/e2e/test_product_launch_hitl.py -q`

Expected: FAIL，当前 reviewer 来自 body 且第二图恢复。

- [ ] **Step 3: 实现 async workflow service**

```python
class ProductLaunchWorkflowService:
    async def start(
        self,
        command: WorkflowCreateCommand,
        request_context: RequestContext,
        *,
        idempotency_key: str | None,
    ) -> WorkflowCreateView:
        registration = self._executions.create_or_get(
            command,
            tenant_id=request_context.tenant_id,
            subject_id=request_context.subject_id,
            idempotency_key=idempotency_key,
        )
        execution = registration.execution
        if not registration.created:
            execution = self._runtime_uow.reconcile_pause_if_needed(
                execution, graph=self._graph
            )
        claim = self._executions.claim_run(
            execution,
            operation="start",
            expected_version=execution.record_version,
            lease_seconds=self._settings.workflow_lease_seconds,
        )
        if not claim.claimed:
            if not registration.created and claim.reason in {
                "terminal", "run_in_progress", "not_startable"
            }:
                return self._views.project_current(claim.execution)
            raise WorkflowConflictError(claim.reason)
        execution = claim.execution
        context = request_context.to_graph_context(run_id=claim.run_id)
        result, execution = await self._invoke_claimed(
            claim,
            command.to_initial_state(execution),
            context,
        )
        return self._views.project_create(execution, result)

    async def resume(
        self,
        workflow_id: str,
        approval_id: str,
        request_context: RequestContext,
    ) -> WorkflowResumeView:
        execution = self._executions.require_for_tenant(
            workflow_id,
            tenant_id=request_context.tenant_id,
        )
        execution = self._runtime_uow.reconcile_pause_if_needed(
            execution, graph=self._graph
        )
        if execution.status in TERMINAL_EXECUTION_STATUSES:
            claim = self._executions.claim_run(
                execution,
                operation="resume",
                expected_version=execution.record_version,
                lease_seconds=self._settings.workflow_lease_seconds,
            )
            assert claim.claimed is False and claim.reason == "terminal"
            return self._views.project_current(claim.execution)
        if execution.status not in {"awaiting_approval", "running"}:
            raise WorkflowConflictError("workflow_not_resumable")
        decision = self._approvals.require_resumable_decision(
            approval_id,
            execution=execution,
            request_context=request_context,
        )
        claim = self._executions.claim_run(
            execution,
            operation="resume",
            expected_version=execution.record_version,
            lease_seconds=self._settings.workflow_lease_seconds,
        )
        if not claim.claimed:
            if claim.reason == "terminal":
                return self._views.project_current(claim.execution)
            raise WorkflowConflictError(claim.reason)
        execution = claim.execution
        context = request_context.to_graph_context(run_id=claim.run_id)
        result, execution = await self._invoke_claimed(
            claim,
            Command(resume=decision.model_dump(mode="json")),
            context,
        )
        return self._views.project_resume(execution, result)

    def get_view(self, workflow_id: str, request_context: RequestContext) -> WorkflowView:
        execution = self._executions.require_for_tenant(
            workflow_id,
            tenant_id=request_context.tenant_id,
        )
        execution = self._runtime_uow.reconcile_pause_if_needed(
            execution, graph=self._graph
        )
        return self._views.project_current(execution)

    async def _invoke_claimed(self, claim: RunClaim, graph_input, context):
        config = {"configurable": {"thread_id": claim.execution.thread_id}}
        try:
            result = await self._graph.ainvoke(
                graph_input,
                config=config,
                context=context,
            )
        except asyncio.CancelledError:
            self._executions.complete_run(
                claim.execution,
                run_id=claim.run_id,
                fencing_token=claim.fencing_token,
                status="cancelled",
                expected_version=claim.execution.record_version,
            )
            raise
        except Exception:
            self._executions.complete_run(
                claim.execution,
                run_id=claim.run_id,
                fencing_token=claim.fencing_token,
                status="failed",
                expected_version=claim.execution.record_version,
            )
            raise
        return result, self._finalize_native_run(claim, result)

    def _finalize_native_run(self, claim: RunClaim, result: dict) -> WorkflowExecution:
        config = {"configurable": {"thread_id": claim.execution.thread_id}}
        snapshot = self._graph.get_state(config)
        if snapshot.interrupts:
            approval = self._approvals.require_for_tenant(
                result["approval_interrupt"]["approval_id"],
                tenant_id=claim.execution.tenant_id,
            )
            return self._runtime_uow.record_pause(
                execution=claim.execution,
                approval_id=approval.id,
                checkpoint_id=snapshot.config["configurable"]["checkpoint_id"],
                interrupt_id=snapshot.interrupts[0].id,
                run_id=claim.run_id,
                fencing_token=claim.fencing_token,
                expected_execution_version=claim.execution.record_version,
                expected_approval_version=approval.record_version,
            )
        return self._executions.complete_run(
            claim.execution,
            run_id=claim.run_id,
            fencing_token=claim.fencing_token,
            status=project_terminal_status(result),
            expected_version=claim.execution.record_version,
        )
```

resume 不接受 decision body；读取已持久化 ApprovalDecision，验证 tenant/digest/checkpoint/interrupt/revision 后先 claim 再调用 `graph.ainvoke(Command(resume=decision), config, context)`。start 重放、resume、get_view 和 approval decision endpoint 在读取 execution 后都先调用同一个 `reconcile_pause_if_needed`；reconciliation 只接纳该 execution 当前 run_id/fencing token 对应的 checkpoint。同一 thread 的两个并发 resume 只有一个获得 run lease；另一个返回 409 `run_in_progress`。`_finalize_native_run` 是每次 ainvoke 的必经路径，pause 通过 UOW 原子记录，terminal 通过 fencing CAS 完成；ainvoke 异常也调用 `complete_run(status="failed")`，旧 worker 不能回写。

- [ ] **Step 4: 投影 semantic snapshot**

兼容 snapshot DTO 由精确 native checkpoint 投影 id/name/version/selected versions；它不是恢复真源。缺失投影不阻塞 native resume，可幂等重建。

- [ ] **Step 5: 运行 GREEN、API 全量并提交**

Run: `python -m pytest tests/e2e/test_product_launch_hitl.py tests/e2e/api -q`

Run: `python -m pytest -q`

```text
git diff --check
git commit -m "功能：保持工作流与审批 API 的原生恢复兼容"
```

---

### Task 5: PublishOperation 状态机与 Outbox

**Files:**
- Create: `backend/src/app/domain/publishing.py`
- Create: `backend/src/app/persistence/repositories/publish_operations.py`
- Create: `backend/src/app/tools/catalog/publish.py`
- Modify: `backend/src/app/runtime/container.py`
- Create: `backend/tests/unit/tools/test_publish_ledger.py`
- Create: `backend/tests/integration/persistence/test_publish_operations.py`

**Interfaces:**
- Produces: seven-state PublishOperation
- Produces: `get_or_create`, `claim`, `commit_outcome`, `begin_reconciliation`

- [ ] **Step 1: 写入状态机 RED 测试**

```python
def test_timeout_moves_operation_to_unknown_without_retry(ledger, adapter):
    operation = ledger.get_or_create(candidate())
    claimed = ledger.claim(operation.id, expected_version=operation.record_version)
    adapter.raise_timeout_after_side_effect = True
    result = execute_publish(claimed, adapter, ledger)
    assert result.status == "unknown"
    assert adapter.calls == 1
```

增加非法转换、stale fencing、同键异 input、outcome/outbox 原子、unknown 必须 reconciliation 测试。

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/unit/tools/test_publish_ledger.py tests/integration/persistence/test_publish_operations.py -q`

Expected: FAIL，账本不存在。

- [ ] **Step 3: 实现状态和仓储事务**

状态固定为 pending、executing、succeeded、failed_retryable、failed_terminal、unknown、reconciling。`claim` CAS 签发 fencing token；`commit_outcome` 在同一锁/事务提交 outcome 与 outbox。Timeout/丢失响应进入 unknown，禁止自动重试。

`ApplicationContainer` 在本任务新增必填 `publish_ledger: PublishOperationLedger`。Publish handler 把 ledger 作为外部副作用真源；Node 17 的 `ToolExecutionCommitStore` 只缓存通用 ToolResult。即使通用缓存提交前崩溃，publish handler 重入时也必须先读取 ledger，已 succeeded/unknown 操作不得再次调用平台 adapter。

- [ ] **Step 4: 运行 GREEN 并提交**

Run: `python -m pytest tests/unit/tools/test_publish_ledger.py tests/integration/persistence/test_publish_operations.py -q`

```text
git diff --check
git commit -m "功能：增加发布操作状态机与 outbox"
```

---

### Task 6: ToolExecutor 与发布节点接线

**Files:**
- Modify: `backend/src/app/tools/executor.py`
- Modify: `backend/src/app/services/listing_versions.py`
- Modify: `backend/src/app/workflows/product_launch/nodes/publish.py`
- Modify: `backend/tests/unit/tools/test_tool_executor.py`
- Modify: `backend/tests/integration/workflows/test_product_launch_graph.py`
- Modify: `backend/tests/integration/workflows/test_native_product_launch_runtime.py`

- [ ] **Step 1: 写入审批与部分发布 RED 测试**

增加：`test_approval_proof_binds_actor_tool_version_and_full_input_hash`、`test_trace_failure_after_ledger_commit_does_not_republish`、`test_partial_publish_resume_replays_committed_operations`、`test_approved_listing_hash_mismatch_blocks_adapter`。再参数化 `succeeded/unknown` ledger 状态，断言 publish handler 重入时 `adapter.calls == 0`；succeeded 只回放 ledger outcome，unknown 返回 reconciliation/escalation，不进入 ToolExecutor handler。

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/unit/tools tests/integration/workflows -k "approval_proof or ledger_commit or partial_publish or hash_mismatch" -q`

Expected: FAIL，发布节点仍直接调用 adapter 或未使用 ledger。

- [ ] **Step 3: 通过 ToolExecutor 调用发布 handler**

每个 marketplace/listing version 生成唯一 operation candidate 和 idempotency key；publish handler 的第一步必须查询 `PublishOperationLedger`，它是发布外部副作用的唯一真源。已 succeeded 操作只投影账本结果；unknown 操作不调用 adapter/ToolExecutor handler并触发 reconciliation/escalation；只有可 claim 的 pending/failed_retryable 才进入 ToolExecutor。`ToolExecutionCommitStore` 只是通用 ToolResult/outbox 缓存，缓存缺失、trace 失败或进程重启都不得覆盖 ledger 决策。保留完整批准版本集合、hash 和 adapter payload 验证。

- [ ] **Step 4: 运行 GREEN、黄金场景并提交**

Run: `python -m pytest tests/unit/tools tests/integration/workflows -q`

Run: `python -m pytest tests/integration/evals/test_product_launch_golden.py -q`

```text
git diff --check
git commit -m "功能：通过发布账本执行审批后的刊登"
```

---

### Task 7: Trace v2 与兼容事件投影

**Files:**
- Modify: `backend/src/app/observability/schema.py`
- Modify: `backend/src/app/persistence/repositories/trace_events.py`
- Modify: `backend/src/app/schemas/api.py`
- Modify: `backend/tests/integration/persistence/test_trace_events.py`
- Create: `backend/tests/e2e/api/test_workflow_events.py`
- Create: `backend/tests/contract/test_trace_event_v2.py`

- [ ] **Step 1: 写入关联与脱敏 RED 测试**

```python
def test_trace_v2_correlates_run_workflow_and_checkpoint(trace_event):
    assert trace_event.run_id
    assert trace_event.workflow_id
    assert trace_event.checkpoint_id
    assert trace_event.sequence >= 1
    assert trace_event.tool_version
    assert trace_event.prompt_version
    assert trace_event.model_version
    assert trace_event.latency_ms >= 0
    assert trace_event.status in {"started", "succeeded", "failed", "cancelled"}


def test_event_api_hides_internal_checkpoint_ids(client, workflow):
    events = client.get(f"/workflows/{workflow.id}/events").json()["events"]
    assert all("thread_id" not in event for event in events)
    assert all("checkpoint_id" not in event for event in events)
```

- [ ] **Step 2: 实现 TraceEvent v2**

增加 `event_id/trace_id/run_id/thread_id/workflow_id/tenant_id/checkpoint_id/task_id/attempt/sequence/schema_version/tool_version/prompt_version/model_version/latency_ms/status/error_code/retry_reason`。不适用的 version/error/retry 字段使用显式 `None`，禁止省略导致消费者猜测；repository 为每个 run 单调分配 sequence 并执行深层 list/dict secret 扫描。API 继续投影 legacy event 视图且隐藏 thread/checkpoint/internal task ID。

- [ ] **Step 3: 运行验证并提交**

Run: `python -m pytest tests/contract/test_trace_event_v2.py tests/integration/persistence/test_trace_events.py tests/e2e/api/test_workflow_events.py -q`

Run: `python -m pytest -q`

```text
git diff --check
git commit -m "功能：升级原生运行时追踪关联字段"
```

---

### Task 8: 版本恢复与 Legacy 退役

**Files:**
- Create: `backend/src/app/runtime/compatibility.py`
- Create: `backend/src/app/workflows/product_launch/version.py`
- Modify: `backend/src/app/workflows/product_launch/graph.py`
- Modify: `backend/src/app/runtime/product_launch.py`
- Modify: `backend/src/app/persistence/repositories/semantic_checkpoints.py`
- Create: `backend/tests/unit/runtime/test_compatibility.py`
- Modify: `backend/tests/e2e/test_product_launch_hitl.py`
- Modify: `docs/progress/2026-07-14-langgraph-standard-runtime-integration.md`

- [ ] **Step 1: 写入版本矩阵 RED 测试**

覆盖 exact revision、SUPPORTED_REVISIONS validator、unsupported 409、state migrator 创建 child checkpoint 并保留 parent、终态 resume 不调用 graph。

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/unit/runtime/test_compatibility.py tests/e2e/test_product_launch_hitl.py -q`

Expected: FAIL，兼容模块不存在且 legacy 第二图仍存在。

- [ ] **Step 3: 实现兼容矩阵**

`GRAPH_REVISION="product-launch/v2"`、`STATE_SCHEMA_VERSION=2`、`SUPPORTED_REVISIONS` 显式列出。无声明时抛 `workflow_revision_unsupported`；迁移器必须写新 checkpoint 分支，不覆盖 parent。

- [ ] **Step 4: 删除 legacy 恢复真源**

删除 `build_product_launch_publish_graph()` 和从 `WorkflowSnapshot.state` 启动恢复的代码；SemanticCheckpoint 只存投影引用。部署前清空进程内 demo 状态，不迁移伪 checkpoint。

- [ ] **Step 5: 最终验证并提交**

```text
python -m pytest tests/unit tests/contract -q
python -m pytest tests/integration/workflows/test_native_product_launch_runtime.py -q
python -m pytest tests/e2e/test_product_launch_hitl.py -q
python -m pytest -q
python -m pytest tests/contract/test_langgraph_manifest.py -q
git diff --check
```

```text
git commit -m "重构：退役旧快照恢复并封闭版本兼容"
git push origin dev-com
```

在 progress log 追加唯一一行 `HITL_FINAL_SHA=` 与当前 `git rev-parse HEAD` 的 40 位小写值，并记录聚焦/全量测试数量、manifest 结果和 reviewer 结论。下一阶段按其 Global Constraints 中的固定 PowerShell 门禁读取。
