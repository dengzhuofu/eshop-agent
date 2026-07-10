# 节点 07：Agent 边界、安全隔离与 LangGraph 工程契约

时间：2026-07-10  
提交：`509ee4f`  
状态：已完成

## 本节点目标

- 为每个 Agent 建立代码层面的职责边界，而不是只写在 prompt 或 PRD 中。
- 建立工具访问安全策略：工具白名单、风险等级、权限、审批、租户隔离和 secret 拦截。
- 按 LangGraph 后续开发方式规范目录和接口：state、node、route、tool、mcp、skill。
- 额外补齐更完整的 Agent 工程最佳实践坑位：prompt、checkpoint、observability、evaluation、memory。

## 已完成内容

### Agent 边界

新增 `backend/app/agents/profiles.py`：

- `AgentProfile`
- `list_agent_profiles`
- `get_agent_profile`

已定义 Agent：

- Supervisor Agent
- Product Research Agent
- Profit Analyst Agent
- Supplier Agent
- Listing Agent
- Localization Agent
- Operations Agent
- Customer Support Agent
- Risk & Review Agent

每个 Agent 定义：

- 角色。
- 展示名称。
- 目的。
- 可调用工具集合。
- 最大风险等级。
- 是否可请求审批。
- 是否受租户隔离约束。
- 禁止接触的数据类别。

### 安全隔离

新增 `backend/app/security/boundary.py`：

- `ToolAccessContext`
- `ToolAccessDecision`
- `AgentBoundaryPolicy`

安全检查包括：

- Agent role 是否存在。
- Tool 是否注册。
- Tool 是否在 Agent 允许列表里。
- 租户是否一致。
- 用户权限是否满足工具权限。
- 工具风险是否超过 Agent 上限。
- 高风险和关键风险工具是否已审批。
- payload 中是否出现 `api_key`、`secret`、`token`、`password`、`credential` 等 secret-like key。

### LangGraph 目录契约

新增目录：

```text
backend/app/agents/
  graphs/
    state.py
    nodes/base.py
    routes/base.py
  mcp/registry.py
  skills/registry.py
```

已定义：

- `CommerceAgentState`
- `create_initial_state`
- `NodeContract`
- `NodeSideEffect`
- `RouteDecision`
- `RouteName`
- `choose_approval_route`
- MCP connector metadata registry
- Agent skill metadata registry

### 补充的最佳实践契约

新增目录：

```text
backend/app/agents/
  prompts/registry.py
  checkpoints/policy.py
  observability/schema.py
  evaluation/registry.py
  memory/policy.py
```

已定义：

- Prompt 版本化元数据。
- Prompt required / forbidden context keys。
- Checkpoint policy。
- Human approval interrupt policy。
- Trace event schema。
- Evaluation scenario registry。
- Workflow / tenant / global memory policy。

## API 更新

新增：

- `GET /agents/profiles`
- `POST /agents/access-check`

说明：

- `/agents/access-check` 是 dry-run，只判断访问是否允许，不执行工具。
- 该接口后续可用于前端调试面板、审批中心、Agent trace 和安全审计。

## 测试覆盖

新增测试：

- `backend/tests/test_agent_boundaries.py`
- `backend/tests/test_security_isolation.py`
- `backend/tests/test_langgraph_contract.py`
- `backend/tests/test_agent_engineering_contract.py`
- `backend/tests/test_agents_api.py`

覆盖内容：

- Listing Agent 可以生成/校验 Listing，但不能发布。
- Customer Support Agent 可以生成客服回复，但不能直接退款。
- Supervisor 可以请求高风险审批。
- 跨租户访问被拒绝。
- 高风险工具未审批时被拒绝。
- 缺少权限时被拒绝。
- secret-like payload 被拒绝。
- route 决策不执行业务副作用。
- MCP 只保存 secret 环境变量名，不保存 secret 值。
- skill 按 Agent role 授权。
- prompt、checkpoint、trace、eval、memory 契约存在。

## 验证记录

命令：

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -v
```

结果：

- 累计后端测试 `42 passed`。

## 重要决策

- Agent 的职责边界必须是后端可执行策略，不只依赖 prompt。
- LangGraph route 函数只负责选择下一节点，不执行工具或外部写操作。
- 后续真实 MCP connector 只能引用 secret 环境变量名，不能保存 secret 值。
- prompt 从第一版开始版本化，后续方便做 prompt diff、回放和评估。
- memory 按 workflow、tenant、global 分层，默认禁止跨租户读取业务记忆。

## 下一节点建议

节点 08：开始实现真正的 LangGraph workflow skeleton。建议先接入 `StateGraph`，把 product research、profit analysis、listing validation、risk review、await approval 这几个节点串成可运行图，但仍保持 publish 动作为审批后的模拟执行。
