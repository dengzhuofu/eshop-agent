# Node 17：类型化工具契约与 ToolExecutor v1 进度

日期：2026-07-13
分支：`codex/node-17-tool-executor`
基线：`106544d7d7dd8585da387c946375ef2f0ad44200`

## 完成范围

- 新增冻结的 `RetryPolicy`、`ToolRequest`、`ToolResult`、`ToolFailure`、`ToolExecutionContext`、`ToolExecutionResult` 和 `ToolHandler` 契约，所有新 Pydantic 契约使用 `extra="forbid"`。
- 扩展 `ToolDefinition`，增加版本、输入/输出模型、超时、重试和 metadata-only 审计策略；`ToolRegistry` 显式拒绝重复工具名称。
- 默认 handler catalog 只绑定 `estimate_profit`、`score_supplier`、`validate_listing`，分别复用现有 profit、supplier 和 mock marketplace 确定性实现。
- `ToolExecutor` 统一执行 registry/handler 检查、AgentBoundaryPolicy、输入/输出 schema、审批证明、超时、显式瞬态重试、幂等、结构化错误和 attempt trace。
- `RepositoryApprovalProofVerifier` 校验审批状态、tenant、workflow、`metadata["tool"]`，并在审批 metadata 绑定幂等键时校验一致性。
- 幂等身份固定为 `(tenant_id, tool_name, tool_version, idempotency_key)` 加规范化输入 hash；每键异步锁防止并发重复执行，只缓存成功结果，回放不产生 handler attempt。

## 文件所有权

- `backend/app/tools/schemas.py`
- `backend/app/tools/executor.py`
- `backend/app/tools/registry.py`
- `backend/app/tools/catalog/__init__.py`
- `backend/app/tools/catalog/base.py`
- `backend/app/tools/catalog/deterministic.py`
- `backend/tests/test_tool_executor.py`
- `docs/superpowers/plans/2026-07-13-tool-executor-v1.md`
- `docs/progress/2026-07-13-node-17-tool-executor.md`

未修改 `backend/app/main.py`、agent profiles、graph state、公共路由或 Product Launch node/workflow/test。Node 17 没有迁移 Product Launch；默认 catalog 中的发布、改价、退款等副作用工具仍返回 `handler_unavailable`，等待后续集成节点接线。

## 错误与重试矩阵

| 错误码 | 触发阶段 | 是否重试 |
| --- | --- | --- |
| `unknown_tool` | registry 查询 | 否 |
| `handler_unavailable` | handler/schema 未绑定 | 否 |
| `access_denied` | role、tenant、permission、risk 或 secret 边界 | 否 |
| `approval_required` | 高风险工具缺少审批 ID | 否 |
| `approval_invalid` | 审批不存在、状态或执行身份绑定无效 | 否 |
| `input_validation_error` | handler 调用前输入 schema | 否 |
| `idempotency_key_required` | 幂等工具缺少稳定键 | 否 |
| `idempotency_conflict` | 同一身份对应不同规范化输入 | 否 |
| `timeout` | `asyncio.wait_for` 超时 | 仅 retry policy 显式列出时 |
| `transient_error` | handler 显式抛出 `TransientToolError` | 仅 retry policy 显式列出时 |
| `output_validation_error` | handler 返回后输出 schema | 否 |
| `handler_error` | 未分类永久异常 | 否 |

每次真实 handler 尝试记录一条 `TraceEventType.TOOL_CALL`。metadata 严格限制为 request/trace ID、工具版本、输入 hash、attempt/max attempts、状态、耗时、错误码、retryable 和幂等键 hash；不记录原始参数、输出或异常文本。

## TDD 证据

- Task 1 RED：`4 failed`，缺少 schema 模块、重复名称拒绝和 v1 registry 字段；GREEN/回归：`7 passed`。
- Task 2 RED：`8 failed`，缺少 catalog/executor；GREEN 筛选集：`8 passed`，扩展确定性服务回归：`25 passed`。
- Task 3 RED：`12 failed`，权限和审批证明尚未执行；GREEN 筛选集：`12 passed`，扩展安全/审批回归：`35 passed`。
- Task 4 首次 RED 因超时尚未实现而持续等待，终止后改为有限等待；最终 RED：`9 failed, 2 passed`。GREEN 筛选集：`11 passed`，完整节点测试：`33 passed`。
- Branch-diff 审查发现缓存回放错误沿用首次 `attempts=1`；新增断言后 RED 为 `1 failed`，修复为回放 `attempts=0` 后 GREEN 为 `1 passed`。

## 评审结果

已按 `requesting-code-review` 流程检查 reviewer 能力，但当前 Worker 会话未提供 subagent dispatch 工具，无法实际发起独立代理评审。随后独立于实现步骤，依据共享设计、ADR 0002、节点计划和 `106544d..HEAD` branch diff 完成逐项自审；发现 1 项 Important（回放 attempt 语义），已通过 RED/GREEN 修复。当前没有未解决的 Critical/Important。

## 真实质量门禁

- 隔离 worktree backend baseline：`83 passed in 1.17s`。
- 最终聚焦回归：`48 passed in 0.17s`。
- 最终完整 backend：`116 passed in 1.39s`。
- `python -m compileall -q app tests`：退出码 0。
- `git diff --check`：退出码 0。
- 未调用真实模型、marketplace、审批或其他外部服务。

## 已知限制

- 幂等缓存和每键锁为进程内实现，不提供跨进程或重启后的持久语义。
- v1 只执行三个确定性低风险 handler；副作用工具和 Product Launch 接线明确留给后续集成节点。
