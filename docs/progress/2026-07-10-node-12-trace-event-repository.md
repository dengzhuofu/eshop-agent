# 节点 12：Trace / Audit 事件仓储

时间：2026-07-10  
实现提交：`781d72d`  
状态：已完成

## 本节点目标

- 为 workflow 增加可查询的 trace / audit 事件记录。
- 让后续前端调试面板可以展示节点执行、工具调用、审批、checkpoint 和失败原因。
- 保持 route 纯决策，事件写入放在 workflow orchestration 层。

## 已完成内容

### Trace 类型扩展

更新 `backend/app/agents/observability/schema.py`：

- 新增 `TraceEventType.CHECKPOINT`

现有 trace 事件类型覆盖：

- `node_start`
- `node_end`
- `checkpoint`
- `tool_decision`
- `tool_call`
- `approval`
- `evaluation`
- `error`

### Trace Event 仓储

新增 `backend/app/repositories/events.py`：

- `TraceEventRepository`
- `get_trace_event_repository`
- `TraceEventConflictError`
- `TraceEventSecurityError`

当前为线程安全内存实现。已覆盖规则：

- 按 workflow 保留事件插入顺序。
- 按 tenant 查询时执行租户隔离。
- metadata 中出现 `api_key`、`secret`、`token`、`password`、`credential` 等 secret-like key 时拒绝记录。
- 事件记录返回深拷贝，避免调用方修改污染仓储。

### Workflow 事件记录

更新 `backend/app/agents/graphs/workflows/product_launch.py`：

Preview 阶段记录：

- 每个 completed step 的 `node_end` 事件。
- 已执行工具的 `tool_call` 事件。
- `approval_requested` 审批事件。
- `snapshot_saved` checkpoint 事件。

Publish resume 阶段记录：

- `publish_listing` 的 `node_end` 事件。
- 每个平台发布工具调用的 `tool_call` 事件。
- 失败恢复时的 `error` 事件。

同时增加 `STEP_AGENT_ROLES` 映射，避免所有节点事件都被错误归为最终的 Supervisor Agent。例如：

- `product_research` -> Product Research Agent
- `profit_analysis` -> Profit Analyst Agent
- `listing_validation` -> Listing Agent
- `risk_review` -> Risk & Review Agent

### Events API

更新 `backend/app/api/routes/workflows.py`：

- 新增 `GET /workflows/{workflow_id}/events`

MVP 阶段仍使用 `demo-tenant` 查询。返回结构：

```json
{
  "workflow_id": "wf_xxx",
  "events": []
}
```

## 测试覆盖

新增：

- `backend/tests/test_trace_events.py`

更新：

- `backend/tests/test_product_launch_graph.py`
- `backend/tests/test_workflows_api.py`

覆盖场景：

- trace repository 按顺序记录事件。
- trace repository 执行 tenant isolation。
- trace repository 拦截 secret-like metadata。
- product launch preview 记录节点、审批和 snapshot 事件。
- product research 事件保留正确 agent role。
- publish resume 记录每个平台的 publish tool call 事件。
- `GET /workflows/{workflow_id}/events` 返回 workflow 事件。

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

- 后端测试累计 `68 passed`。

## 重要取舍

- 当前事件记录是 coarse-grained workflow trace，不是完整 OpenTelemetry 分布式追踪。
- 当前事件仓储是内存实现，后续需要替换为数据库或日志系统。
- 当前事件写入放在 workflow orchestration 层，避免 graph route 和 node 混入太多横切关注点。
- 当前 API 只按 demo tenant 查询，后续接认证后应从登录上下文获取 tenant。

## 下一节点建议

节点 13：供应商评估 Agent 接入主链路。

建议范围：

- 把 PRD 中的 Supplier Agent 从独立 deterministic service 接入 product launch graph。
- 在 `profit_analysis` 和 `listing_validation` 之间加入 `supplier_evaluation` 节点。
- 将供应商评分写入 state、snapshot、trace。
- 若供应商质量风险过高，Risk Review 应把供应商风险纳入审批原因。
- 覆盖供应商评分、低质量供应商风险、trace/snapshot 保存测试。
