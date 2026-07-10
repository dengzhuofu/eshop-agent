# 节点 10：审批后 Mock 发布恢复

时间：2026-07-10  
实现提交：`0b3ae86`  
状态：已完成

## 本节点目标

- 在 Node 09 的审批请求闭环之后，补上“审批通过后恢复 workflow 执行”的最小闭环。
- 调用现有 mock marketplace adapter 完成模拟发布。
- 继续保证没有真实平台写入、没有绕过审批的高风险动作。

## 已完成内容

### State 扩展

更新 `backend/app/agents/graphs/state.py`：

- 新增 `publish_results`

该字段保存每个平台的 mock 发布结果，后续可替换为真实发布任务结果或发布审计记录。

### 审批元数据补齐

更新 `await_approval_node`：

- 审批请求 metadata 新增 `target_price`

原因：

- 当前 MVP 尚未引入 workflow 持久化仓储。
- 发布恢复需要从审批请求中重建确定性的 listing draft。
- 后续接入数据库后，应改为从 workflow snapshot / checkpoint 恢复，而不是依赖 approval metadata 承载业务快照。

### 发布恢复节点

新增 `publish_listing_node`：

- 加载 `approval_request_id` 对应的审批请求。
- 审批不存在时返回 failed。
- 审批不是 `approved` 时返回 failed。
- 审批通过后，再通过 `AgentBoundaryPolicy` 校验 `publish_listing` 工具访问。
- 为每个平台调用 mock adapter 的 `publish_listing`。
- 使用稳定幂等键：

```text
{approval_id}:{marketplace}
```

这样同一审批请求重复恢复时，mock 发布结果保持稳定。

### Publish Resume Workflow

更新 `backend/app/agents/graphs/workflows/product_launch.py`：

- 新增 `build_product_launch_publish_graph`
- 新增 `run_product_launch_publish_resume`

当前恢复图结构：

```text
START
  -> publish_listing
  -> END
```

这仍然是 MVP 版本。后续可以扩展为：

```text
approval_check -> publish_listing -> audit -> monitor
```

### Workflow Resume API

更新 `backend/app/api/routes/workflows.py`：

- 新增 `POST /workflows/{workflow_id}/resume`

请求体：

```json
{
  "approval_request_id": "appr_xxx"
}
```

行为：

- 审批请求不存在：`404`
- 审批请求不属于当前 workflow：`409`
- 审批未通过：`409`
- 审批通过：执行 mock 发布并返回 `publish_results`

## 测试覆盖

更新：

- `backend/tests/test_product_launch_graph.py`
- `backend/tests/test_workflows_api.py`

覆盖场景：

- 未审批时不能恢复发布。
- 审批通过后可以发布到多个 mock marketplace。
- 重复恢复同一审批请求时发布结果稳定。
- workflow resume API 在审批通过后返回 completed。
- workflow resume API 在审批未通过时返回 409。

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

- 后端测试累计 `54 passed`。

## 重要取舍

- 当前只执行 mock 发布，不接真实 Amazon / Shopify / TikTok Shop API。
- 当前发布结果不写数据库，只作为 graph state 和 API 响应返回；生产版本需要发布任务表、审计日志和失败重试队列。
- 当前从 approval metadata 重建 listing draft，是 MVP 下没有 workflow checkpoint 持久化时的折中方案；后续应迁移到 checkpoint/snapshot 恢复。
- 发布节点再次调用 `AgentBoundaryPolicy`，避免“审批通过”被误用为绕过工具权限的通行证。

## 下一节点建议

节点 11：workflow checkpoint / snapshot 仓储。

建议范围：

- 增加 workflow snapshot repository。
- 在关键节点保存 state 快照。
- `POST /workflows/{workflow_id}/resume` 改为从 snapshot 恢复，而不是从 approval metadata 重建。
- 增加失败恢复、重复恢复、跨租户读取拦截测试。
- 为后续真实数据库和 LangGraph checkpoint saver 预留替换点。
