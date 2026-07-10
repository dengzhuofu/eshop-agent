# ADR 0001：Agent 分层、Route 语义与工程取舍

日期：2026-07-10  
状态：Accepted

## 背景

本项目主要使用 LangGraph 实现跨境电商全链路 Agent 平台。用户提到需要定义 `tool`、`node`、`state`、`route`、`mcp`、`skill` 等 Agent 开发必要结构，但这些词不能被机械理解为“目录越多越专业”。如果分层没有执行语义、边界和测试，最后只会变成空壳。

本 ADR 用来固定项目里的分层含义，尤其说明 `route` 的语义，并规定后续每个节点开发前的判断标准。

## 结论

### 1. State

`state` 是 LangGraph 的共享业务状态。它不是数据库模型，也不是请求 DTO。

职责：

- 保存 workflow 执行过程中的必要上下文。
- 在 node 之间传递业务结果。
- 记录 approval、risk、evidence、tool_calls、completed_steps 等可回放信息。

约束：

- 不存 raw secret。
- 不跨租户混用。
- 不把所有数据库字段搬进 state，只保留图执行需要的信息。

### 2. Node

`node` 是 LangGraph 的工作单元。它读取 state，返回 state update。

职责：

- 执行一个清晰业务步骤，例如 product research、profit analysis、listing validation、risk review。
- 调用确定性服务或受控 tool。
- 产出可测试的状态更新。

约束：

- 不直接越权访问数据库、secret 或真实平台 API。
- 不直接做高风险外部写操作。
- 不在节点里隐藏 route 决策。

### 3. Route

本项目里的 `route` 指 **LangGraph 图中的条件路由函数**，不是 FastAPI 的 HTTP route。

职责：

- 根据当前 state 决定下一节点。
- 表达工作流分支，例如 `await_approval`、`complete`、`retry`、`fail`。

约束：

- route 必须是确定性逻辑。
- route 不调用工具。
- route 不写数据库。
- route 不执行外部副作用。
- route 不做复杂业务计算；复杂判断应在前一个 node 中产出明确 state 字段。

HTTP API route 放在 `backend/app/api/routes/`，Graph route 放在 `backend/app/agents/graphs/routes/`，两者名称相同但语义不同。

### 4. Tool

`tool` 是 Agent 能请求的受控能力，不等于任意 Python 函数。

职责：

- 暴露明确输入输出。
- 记录风险等级、权限、是否需要审批、是否幂等。
- 作为 Agent 和业务系统之间的安全边界。

约束：

- Agent 只能请求 ToolRegistry 里注册的工具。
- 高风险和关键风险工具必须审批。
- 工具层负责权限、校验、幂等和审计。

### 5. MCP

`mcp` 是未来外部系统连接器的扩展位，不是 MVP 必须接真实外部服务。

职责：

- 描述将来接入 marketplace、support knowledge base、文件系统、监控系统等外部能力时的连接器元数据。
- 保存 secret 环境变量名，而不是 secret 值。

约束：

- MVP 阶段只保留 metadata registry。
- 不为了展示“用了 MCP”而提前接入不必要服务。

### 6. Skill

`skill` 是 Agent 的领域操作说明或策略包，不等于工具。

职责：

- 绑定特定 Agent role。
- 表达 Listing 合规、客服 RAG、利润复核等领域规则。
- 后续可以映射为 prompt 片段、规则集或可加载说明。

约束：

- Skill 不能绕过 ToolRegistry。
- Skill 不能授予 Agent 原本没有的工具权限。

## 补充必要层

只定义 `tool/node/state/route/mcp/skill` 还不够。生产化 Agent 还需要以下层：

- `profiles`：定义每个 Agent 的角色、目的、工具白名单、风险边界。
- `security`：执行租户隔离、权限、审批和 secret 拦截。
- `prompts`：prompt 版本化，声明 required / forbidden context。
- `checkpoints`：定义快照、失败恢复、人审中断点。
- `observability`：记录 workflow、tenant、agent、tool、approval、evaluation 事件。
- `evaluation`：定义回归评估场景，防止 prompt 或工具变更退化。
- `memory`：区分 workflow、tenant、global 记忆作用域，避免跨租户泄漏。
- `adapters`：隔离不同 marketplace 的规则和真实 API 差异。

## 后续节点开发检查

每开发一个链路节点，都要先回答：

1. 这个节点是否真的需要成为 LangGraph node，还是普通 service/tool 就够了？
2. 这个节点读写哪些 state 字段？
3. 这个节点是否调用 tool？如果调用，风险等级和权限是什么？
4. 这个节点是否可能触发审批？
5. 这个节点是否需要 checkpoint？
6. 这个节点是否会接触 tenant 数据、PII、支付信息或 secret？
7. 这个节点失败后能否重试？是否幂等？
8. 这个节点的输出如何被 trace 和 evaluation 覆盖？
9. route 是否只是选择下一步，而不是偷偷执行副作用？
10. 是否有测试证明以上边界？

## 取舍

为了平衡质量和 token / 开发成本：

- 每个节点不写长篇设计说明，但必须有测试和节点总结日志。
- 复杂设计进入 ADR，避免在聊天里反复讨论同一个判断。
- MVP 先实现确定性 skeleton，再逐步接入真实 LLM、RAG、持久化和审批恢复。
- 对不确定是否必要的层，先用 metadata registry 固定边界，不提前接真实外部服务。

