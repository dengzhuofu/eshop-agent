# 节点 08：Product Launch LangGraph Workflow Skeleton

时间：2026-07-10  
提交：`dbfc0ea`  
状态：已完成

## 本节点目标

- 将前面定义好的 state、node、route、approval 契约接成真正可运行的 LangGraph workflow。
- 打通 MVP 商品启动主链路的第一版确定性图：
  - product_research
  - profit_analysis
  - listing_validation
  - risk_review
  - await_approval
- 保持 publish_listing 为审批后的动作，本节点不执行真实发布。

## 已完成内容

### State 扩展

更新 `backend/app/agents/graphs/state.py`，为 `CommerceAgentState` 增加：

- `product_idea`
- `target_marketplaces`
- `target_price`
- `risk_preference`
- `profit_estimate`
- `listing_validations`
- `approval_reasons`
- `completed_steps`

### LangGraph Nodes

新增 `backend/app/agents/graphs/nodes/product_launch.py`：

- `product_research_node`
- `profit_analysis_node`
- `listing_validation_node`
- `risk_review_node`
- `await_approval_node`
- `complete_node`

节点原则：

- 节点返回 state update，不直接原地修改输入 state。
- 数学计算和 Listing 校验继续走确定性服务与 mock adapter。
- 风险审核节点只设置审批需求，不执行发布。

### LangGraph Routes

新增 `backend/app/agents/graphs/routes/product_launch.py`：

- `route_after_risk_review`

路由原则：

- 只根据 state 决定下一节点。
- 不执行工具。
- 不执行外部副作用。

### Workflow Builder

新增 `backend/app/agents/graphs/workflows/product_launch.py`：

- `build_product_launch_graph`
- `run_product_launch_preview`

当前图结构：

```text
START
  -> product_research
  -> profit_analysis
  -> listing_validation
  -> risk_review
      -> await_approval -> END
      -> complete -> END
```

因为当前 publish_listing 是高风险动作，所以 MVP preview 默认进入 `await_approval`。

### API 集成

更新 `backend/app/api/routes/workflows.py`：

- `POST /workflows` 不再复制业务流程逻辑。
- API 调用 `run_product_launch_preview` 获取图执行结果。
- 保持原有响应字段，并新增 `completed_steps`。

## 测试覆盖

新增 `backend/tests/test_product_launch_graph.py`：

- 验证图最终进入 `awaiting_approval`。
- 验证 `approval_reasons=["publish_listing"]`。
- 验证按顺序记录完成节点。
- 验证记录 mock research evidence。
- 验证利润测算进入 state。
- 验证三个目标平台都产生 Listing validation。

## 验证记录

命令：

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -v
```

结果：

- 累计后端测试 `45 passed`。

## 重要决策

- 当前 graph 是确定性 skeleton，不调用真实 LLM，也不执行真实平台写操作。
- `POST /workflows` 已经变成 graph-backed API，避免 API 和 LangGraph 工作流逻辑分叉。
- 审批中断点现在是实际图节点 `await_approval`，后续可以接 LangGraph checkpoint / interrupt / 人审 UI。

## 下一节点建议

节点 09：实现审批请求模型与审批 API。建议先做内存或轻量 repository 版本，让 `await_approval` 节点生成可查询的 approval request，并增加 approve/reject 后的图恢复入口。
