# 节点 11：Workflow Snapshot 仓储

时间：2026-07-10  
实现提交：`eb929fa`  
状态：已完成

## 本节点目标

- 将 workflow 恢复从 approval metadata 重建，升级为从 workflow snapshot 恢复。
- 为后续 LangGraph checkpoint saver、失败恢复、审计回放和真实数据库持久化预留边界。
- 继续保持 route 纯决策，snapshot 写入放在 workflow orchestration 层。

## 已完成内容

### Snapshot 领域模型

新增 `backend/app/domain/snapshots.py`：

- `WorkflowSnapshot`

字段包括：

- `workflow_id`
- `tenant_id`
- `checkpoint_name`
- `version`
- `state`
- `created_at`

### Snapshot 仓储

新增 `backend/app/repositories/snapshots.py`：

- `WorkflowSnapshotRepository`
- `get_workflow_snapshot_repository`
- `WorkflowSnapshotConflictError`
- `WorkflowSnapshotSecurityError`

当前为线程安全内存实现，用于 MVP 和测试阶段。后续可以替换为 SQLite/Postgres/Redis 或 LangGraph checkpointer，而调用方不需要直接关心底层存储。

已覆盖规则：

- 同一 workflow 的 snapshot 按版本递增。
- 同一 workflow、同一 checkpoint、同一 state 重复保存时幂等返回已有版本。
- 读取 snapshot 时强制 tenant 匹配。
- snapshot state 中出现 `api_key`、`secret`、`token`、`password`、`credential` 等 secret-like key 时拒绝保存。
- 保存时对 state 做深拷贝，避免调用方后续修改污染快照。

### Preview Checkpoint 保存

更新 `run_product_launch_preview`：

- LangGraph preview 执行完成后，如果最终状态是 `awaiting_approval`，保存 `await_approval` snapshot。
- 保存位置在 workflow orchestration 层，而不是 graph route。

这样保留了 ADR 0001 中的约束：

- route 只做下一步选择。
- node 不隐藏无关持久化副作用。
- checkpoint/snapshot 有独立边界。

### Snapshot-backed Resume

更新 `run_product_launch_publish_resume`：

- 先加载 approval request。
- 再用 approval 的 `workflow_id` 和 `tenant_id` 加载最新 snapshot。
- 如果 snapshot 不存在，返回 failed state：`workflow snapshot not found`。
- 如果 snapshot 存在，用 snapshot state 作为恢复源。
- approval 只覆盖当前审批状态、审批原因和风险等级。

这解决了 Node 10 的 MVP 折中：发布恢复不再依赖 approval metadata 承载业务快照。

### Workflow API

更新 `POST /workflows` 响应：

- 新增 `snapshot` 元数据：
  - `id`
  - `checkpoint_name`
  - `version`

`POST /workflows/{workflow_id}/resume` 继续沿用原错误映射：

- snapshot 缺失时返回 `409`
- 审批未通过时返回 `409`
- 审批不存在时返回 `404`

## 测试覆盖

新增：

- `backend/tests/test_workflow_snapshots.py`

更新：

- `backend/tests/test_product_launch_graph.py`
- `backend/tests/test_workflows_api.py`

覆盖场景：

- snapshot 保存、版本递增和幂等重复保存。
- snapshot 租户隔离。
- snapshot secret-like key 拦截。
- snapshot 防止调用方后续 mutation 污染。
- product launch preview 保存 `await_approval` snapshot。
- publish resume 使用 snapshot，而不是 approval metadata。
- workflow 创建响应返回 snapshot 元数据。
- snapshot 缺失时 resume 返回 409。

## 验证记录

命令：

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -v
```

执行目录：

```text
backend/
```

结果：

- 后端测试累计 `62 passed`。

## 重要取舍

- 当前 snapshot repository 是业务快照层，不等同于 LangGraph 原生 checkpointer。
- MVP 暂时只保存 `await_approval` checkpoint；后续可以扩展到失败节点、发布后节点和复盘节点。
- 当前仍是内存仓储，重启会丢失；但 repository 边界已经固定，迁移持久化实现时不需要改 API 或 graph 调用方。
- approval metadata 保留兼容字段，但不再作为 resume 的业务状态来源。

## 下一节点建议

节点 12：可观测性 trace / audit 事件仓储。

建议范围：

- 增加 trace event repository。
- 在关键节点记录 node/tool/approval/snapshot/publish 事件。
- API 暴露 `GET /workflows/{workflow_id}/events`。
- 确保事件包含 workflow、tenant、agent、event_type、name、metadata、created_at。
- 覆盖发布审批、snapshot 保存、publish tool call、失败恢复等事件测试。
