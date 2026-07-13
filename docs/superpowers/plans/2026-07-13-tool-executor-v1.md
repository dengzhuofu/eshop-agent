# Typed Tool Contract And ToolExecutor v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 Node 17 类型化工具契约和统一 ToolExecutor v1，覆盖边界策略、schema、审批证明、超时、显式瞬态重试、幂等和 attempt trace。

**Architecture:** Registry 保存工具元数据与可选 Pydantic 输入/输出模型；HandlerCatalog 只绑定 `estimate_profit`、`score_supplier`、`validate_listing` 三个确定性低风险 handler。ToolExecutor 统一完成拒绝、验证、调用、重试、幂等和结果归一化；未绑定 handler 的工具可发现但不可执行。

**Tech Stack:** Python 3.12, Pydantic 2.11.7, pytest 8.4.1, asyncio, current approval/trace repositories.

## Global Constraints

- 分支：`codex/node-17-tool-executor`，基线必须包含提交 `5cc8bc5`。
- 只创建/修改 `backend/app/tools/schemas.py`、`executor.py`、`registry.py`、`catalog/`、`backend/tests/test_tool_executor.py`、Node 17 进度日志。
- 禁止修改 `backend/app/main.py`、`backend/app/agents/profiles.py`、`backend/app/agents/graphs/state.py`、公共路由和任何 Product Launch node/workflow/test。
- 不增加共享 enum，不迁移 Product Launch；副作用工具在本分支保持 `handler_unavailable`。
- Trace 只记录 ID、版本、hash、attempt、状态、耗时和错误类别，不记录原始参数、输出或异常文本。
- 只有 retry policy 明确列出的 `transient_error` / `timeout` 可重试；权限、审批、schema、幂等冲突和永久异常不重试。
- 幂等缓存只保存成功结果；失败不得缓存。
- Git 提交描述使用中文。
- 所有 pytest 命令从 `backend/` 执行，解释器固定为 `C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`。

---

## Files

- Create: `backend/app/tools/schemas.py`
- Create: `backend/app/tools/executor.py`
- Create: `backend/app/tools/catalog/__init__.py`
- Create: `backend/app/tools/catalog/base.py`
- Create: `backend/app/tools/catalog/deterministic.py`
- Modify: `backend/app/tools/registry.py`
- Create: `backend/tests/test_tool_executor.py`
- Create: `docs/progress/2026-07-13-node-17-tool-executor.md`

## Frozen Interfaces

```python
ToolFailureCode = Literal[
    "unknown_tool", "handler_unavailable", "access_denied",
    "approval_required", "approval_invalid", "input_validation_error",
    "idempotency_key_required", "idempotency_conflict", "timeout",
    "transient_error", "output_validation_error", "handler_error",
]


class RetryPolicy(BaseModel):
    max_attempts: int = Field(ge=1, le=5)
    initial_backoff_seconds: float = Field(ge=0, le=5)
    backoff_multiplier: float = Field(ge=1, le=4)
    max_backoff_seconds: float = Field(ge=0, le=30)
    retry_on: frozenset[Literal["transient_error", "timeout"]]


class ToolRequest(BaseModel):
    request_id: str
    tool_name: str
    tenant_id: str
    target_tenant_id: str
    workflow_id: str
    actor_id: str
    agent_role: AgentRole
    trace_id: str
    actor_permissions: set[str]
    arguments: dict[str, Any]
    approval_id: str | None = None
    idempotency_key: str | None = None


class ToolResult(BaseModel):
    ok: Literal[True]
    request_id: str
    tool_name: str
    tool_version: str
    tenant_id: str
    workflow_id: str
    trace_id: str
    output: dict[str, Any]
    attempts: int
    duration_ms: int
    replayed: bool


class ToolFailure(BaseModel):
    ok: Literal[False]
    request_id: str
    tool_name: str
    tool_version: str | None
    tenant_id: str
    workflow_id: str
    trace_id: str
    code: ToolFailureCode
    message: str
    details: list[str]
    retryable: bool
    attempts: int
    duration_ms: int


ToolExecutionResult = ToolResult | ToolFailure
ToolHandler = Callable[[BaseModel, ToolExecutionContext], Awaitable[BaseModel | Mapping[str, Any]]]
```

`ToolDefinition` 新增：

```python
version: str = "1.0.0"
input_model: type[BaseModel] | None = None
output_model: type[BaseModel] | None = None
timeout_seconds: float = 5.0
retry_policy: RetryPolicy
audit_policy: Literal["metadata_only"] = "metadata_only"
```

公共对象：

```python
class ToolHandlerCatalog:
    def register(self, tool_name: str, handler: ToolHandler) -> None: ...
    def get(self, tool_name: str) -> ToolHandler: ...
    def names(self) -> set[str]: ...


class ToolExecutor:
    def __init__(self, *, registry: ToolRegistry, handlers: ToolHandlerCatalog,
                 boundary_policy: AgentBoundaryPolicy,
                 approval_verifier: ApprovalProofVerifier,
                 idempotency_store: InMemoryIdempotencyStore,
                 trace_repository: TraceEventRepository,
                 sleeper=asyncio.sleep, clock=time.perf_counter) -> None: ...
    async def execute(self, request: ToolRequest) -> ToolExecutionResult: ...
```

`RepositoryApprovalProofVerifier` 必须校验 approval status、tenant、workflow、`metadata["tool"]`，并在 metadata 存在 idempotency key 时校验一致性。

Attempt 使用 `TraceEventType.TOOL_CALL`，metadata 固定为：`request_id`、`trace_id`、`tool_version`、`input_hash`、`attempt`、`max_attempts`、`status`、`duration_ms`、`failure_code`、`retryable`、`idempotency_key_hash`。

### Task 1: Typed Schemas And Registry

**Files:** Create schemas/test; modify registry.

- [x] **Step 1: Write RED tests** for retry bounds, duplicate tool names and v1 metadata/schema on `estimate_profit`, `score_supplier`, `validate_listing`.
- [x] **Step 2: Verify RED**:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_tool_executor.py -k "contract or registry or retry_policy" -v
```

Expected: FAIL because schemas/fields are absent.

- [x] **Step 3: Implement GREEN** with `ConfigDict(extra="forbid")`. Reuse `ProfitInput/ProfitEstimate`, `SupplierInput/SupplierScore`, `ListingDraft/ValidationResult` as registered model classes. Existing tool names, risks and permissions remain unchanged.
- [x] **Step 4: Verify and commit**; expected PASS. Commit: `feat: 增加类型化工具契约与注册定义`.

### Task 2: Handler Catalog And Schema Execution

**Files:** Create catalog/executor; modify test.

- [x] **Step 1: Write RED tests** for three default handlers, duplicate handler registration, unknown tool, unbound handler, invalid input not invoking handler and invalid output normalization.
- [x] **Step 2: Verify RED** with `pytest tests/test_tool_executor.py -k "handler or schema or unknown" -v`; expected FAIL.
- [x] **Step 3: Implement GREEN**. Async wrappers call `estimate_profit`, `score_supplier`, and marketplace adapter `validate_listing`; executor validates input before handler and output after handler.
- [x] **Step 4: Verify and commit**; expected PASS. Commit: `feat: 增加确定性工具处理器目录`.

### Task 3: Permission And Approval Boundary

**Files:** Modify executor/test.

- [x] **Step 1: Write RED tests** for wrong role, tenant mismatch, missing permission, nested secret, missing/pending/rejected/wrong-tenant/wrong-workflow/wrong-tool approval proof and a valid approved proof.
- [x] **Step 2: Verify RED** with `pytest tests/test_tool_executor.py -k "access or tenant or permission or approval or secret" -v`; expected FAIL.
- [x] **Step 3: Implement GREEN**. First evaluate policy with `approved=False`; non-approval reasons fail immediately. For approval tools verify repository proof, then re-evaluate with `approved=True`.
- [x] **Step 4: Verify and commit**; expected PASS. Commit: `feat: 增加工具权限与审批执行边界`.

### Task 4: Timeout, Retry, Idempotency And Trace

**Files:** Modify executor/test.

- [x] **Step 1: Write RED tests** for timeout, two transient failures then success, permanent error no retry, missing key, same key/input replay, same key/different input conflict, concurrent same key one handler call, attempt trace and sanitized errors.
- [x] **Step 2: Verify RED** with `pytest tests/test_tool_executor.py -k "timeout or retry or idempotency or trace or sanitized" -v`; expected FAIL.
- [x] **Step 3: Implement GREEN** with `asyncio.wait_for`, injected sleeper, bounded exponential backoff and per-key lock/cache. Idempotency identity is `(tenant_id, tool_name, tool_version, idempotency_key)` plus canonical input hash.
- [x] **Step 4: Verify and commit**; expected PASS. Commit: `feat: 增加工具重试幂等与尝试追踪`.

### Task 5: Progress Log And Quality Gates

**Files:** Create progress log.

- [x] Run focused regression:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_tool_executor.py tests/test_tool_registry.py tests/test_agent_boundaries.py tests/test_security_isolation.py tests/test_trace_events.py -v
```

- [x] Run full `pytest -v` and repository-root `git diff --check`.
- [x] Request independent review against shared design, ADR 0002 and branch diff; resolve all Critical/Important issues.
- [x] Write Chinese log with owned files, frozen interfaces, handler scope, error matrix, TDD evidence, real counts, review outcome and explicit note that Product Launch was not migrated.
- [x] Commit and push: `docs: 记录第十七节点工具执行器进展`; `git push -u origin codex/node-17-tool-executor`.
