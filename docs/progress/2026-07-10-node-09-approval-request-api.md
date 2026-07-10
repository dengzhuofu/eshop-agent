# 节点 09：审批请求模型与 API

时间：2026-07-10  
实现提交：`b350661`  
状态：已完成

## 本节点目标

- 将 `await_approval` 从单纯的 workflow 状态升级为可查询、可批准、可驳回的审批请求。
- 为后续运营控制台、人审恢复、发布前确认预留稳定接口。
- 继续保持 MVP 不执行真实平台发布，也不调用真实外部服务。

## 已完成内容

### 审批领域模型

新增 `backend/app/domain/approvals.py`：

- `ApprovalRequest`
- `ApprovalActionRequest`

审批请求记录以下关键字段：

- workflow、tenant、resource 关联信息
- 审批原因 `reason_codes`
- 风险等级 `risk_level`
- 当前状态 `pending / approved / rejected`
- 创建时间、审核人、审核时间、审核备注
- 可扩展 metadata

### 审批仓储

新增 `backend/app/repositories/approvals.py`：

- `ApprovalRepository`
- `get_approval_repository`
- `ApprovalConflictError`

当前实现是线程安全的内存仓储，用于 MVP 和测试阶段。它刻意放在 repository 边界下，后续可以替换为 SQLite/Postgres/Redis，而不需要改动 graph 节点和 API 的调用方式。

已覆盖的状态规则：

- 同一 `approval_id` 重复创建时幂等返回已有请求。
- `pending -> approved` 合法。
- `pending -> rejected` 合法。
- 重复 approve / reject 同一终态请求幂等返回。
- `approved -> rejected`、`rejected -> approved` 返回冲突。

### LangGraph 审批检查点

更新 `backend/app/agents/graphs/nodes/product_launch.py`：

- `await_approval_node` 现在会幂等创建审批请求。
- state 中返回：
  - `approval_request_id`
  - `approval_request`

工程取舍：

- `await_approval` 是明确的人审检查点，因此允许受控、幂等的仓储写入。
- `route_after_risk_review` 仍保持纯决策函数，不执行工具、不写仓储、不产生外部副作用。

### 审批 API

新增 `backend/app/api/routes/approvals.py` 并注册到 `backend/app/main.py`：

- `GET /approvals`
- `GET /approvals/{approval_id}`
- `POST /approvals/{approval_id}/approve`
- `POST /approvals/{approval_id}/reject`

错误语义：

- 不存在的审批请求返回 `404`。
- 非法终态切换返回 `409`。

### Workflow API 集成

更新 `backend/app/api/routes/workflows.py`：

- `POST /workflows` 响应新增：
  - `approval_request_id`
  - `approval_request`

这样前端或后续 Agent 控制台在创建商品启动 workflow 后，可以直接跳转到对应审批详情。

## 测试覆盖

新增：

- `backend/tests/test_approval_repository.py`
- `backend/tests/test_approvals_api.py`

更新：

- `backend/tests/test_product_launch_graph.py`
- `backend/tests/test_workflows_api.py`

覆盖场景：

- 审批请求幂等创建。
- approve / reject 状态流转。
- 非法终态切换冲突。
- graph 创建可查询的审批请求。
- `/approvals` API 的列表、详情、批准、驳回、404、409 行为。
- `/workflows` 返回审批请求 ID 和请求快照。

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

- 后端测试累计 `50 passed`。

## 重要取舍

- 当前审批仓储是内存实现，不适合生产持久化；但边界已经放在 repository 层，后续迁移数据库时只需要替换实现。
- 本节点不做真实发布恢复，只完成审批请求闭环。原因是发布恢复需要进一步定义 publish action 的幂等键、平台 adapter 写入语义、失败重试和审计记录。
- API 暂未加入真实鉴权和租户过滤；当前仍是 demo tenant/MVP 语义，后续接入认证后需要让 `/approvals` 默认只返回当前租户的数据。

## 下一节点建议

节点 10：审批后的 graph 恢复与 mock 发布执行。

建议范围：

- 增加 `publish_listing` graph 节点或 workflow resume 函数。
- 只允许 `approved` 的审批请求进入发布路径。
- 调用现有 mock marketplace adapter 的 `publish_listing`，仍不接真实平台。
- 为每个平台生成幂等发布结果和审计事件。
- 覆盖 approve 后可执行、reject 后不可执行、重复执行幂等、平台发布失败可重试等测试。
