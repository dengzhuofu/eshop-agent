# 节点 05：工具注册中心与最小 Workflow API

时间：2026-07-09  
提交：`24f7403`  
状态：已完成

## 本节点目标

- 建立工具注册中心，记录工具风险等级、权限和是否需要人工审批。
- 暴露 marketplace rules API，让前端和后续 Agent 能读取平台规则。
- 暴露最小 workflow preview API，把 mock adapter、利润测算和审批策略串起来。

## 已完成内容

- 新增 `backend/app/tools/registry.py`：
  - `ToolDefinition`
  - `ToolRegistry`
  - `build_default_registry`
- 新增 `backend/app/api/routes/marketplaces.py`：
  - `GET /marketplaces/{marketplace}/rules`
- 新增 `backend/app/api/routes/workflows.py`：
  - `POST /workflows`
- 更新 `backend/app/main.py`，注册 marketplace 和 workflow 路由。
- 新增测试：
  - `backend/tests/test_tool_registry.py`
  - `backend/tests/test_workflows_api.py`

## 工具风险策略

- `publish_listing`：高风险，需要审批，权限 `listing:publish`。
- `update_price`：高风险，需要审批，权限 `price:update`。
- `issue_refund`：关键风险，需要审批，权限 `refund:issue`。
- `get_orders`：低风险，不需要审批，权限 `workflow:read`。
- `estimate_profit`：低风险，不需要审批，走确定性计算服务。

## API 行为

- `GET /marketplaces/amazon/rules` 返回 Amazon-like 标题长度、bullet point 等规则。
- `POST /workflows` 返回 deterministic preview：
  - `workflow_id`
  - `state=awaiting_approval`
  - `profit_estimate`
  - 三个平台的 `listing_validations`
  - `approval_required=true`
  - `approval_reasons=["publish_listing"]`

## 验证记录

命令：

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -v
```

结果：

- 工具注册中心测试通过。
- marketplace rules API 测试通过。
- workflow preview API 测试通过。
- 累计后端测试 `21 passed`。

## 重要决策

- 第一版 workflow API 先返回 deterministic preview，不直接调用真实 LLM，便于建立可测试业务骨架。
- 高风险 publish 动作在预览阶段就标记为需要审批，符合 PRD 的 human-in-the-loop 边界。
- 平台规则通过 API 暴露，为后续前端 Listing Workspace 和审批 diff 做准备。

## 下一节点

节点 06：最终验证、README 补充、Git remote 检查，并尝试推送到 `dengzhuofu/eshop-agent.git`。
