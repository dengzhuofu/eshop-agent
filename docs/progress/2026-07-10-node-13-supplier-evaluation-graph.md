# 节点 13：Supplier Agent 接入主链路

时间：2026-07-10  
实现提交：`79251d6`  
状态：已完成

## 本节点目标

- 将 PRD 主链路中的 Supplier Agent 从独立 deterministic service 接入 Product Launch LangGraph。
- 让供应商评分进入 workflow state、snapshot、trace 和 API 响应。
- 让 Risk Review 能基于供应商风险追加审批原因。

## 已完成内容

### State 扩展

更新 `backend/app/agents/graphs/state.py`：

- `supplier_evaluations`
- `selected_supplier_id`
- `supplier_risk_level`

这些字段会进入 workflow snapshot，因此后续恢复发布不需要从 approval metadata 重建供应商状态。

### Supplier Evaluation Node

更新 `backend/app/agents/graphs/nodes/product_launch.py`：

- 新增 `supplier_evaluation_node`
- 复用现有 `score_supplier` deterministic service
- 默认评分两个 mock supplier：
  - `SUP-1`：低风险，推荐
  - `SUP-2`：高风险，不推荐
- `risk_preference="supplier_risk"` 时使用高风险供应商场景，方便测试 Risk Review 行为

节点输出：

- 供应商评分列表
- 选中供应商
- 供应商风险等级
- `score_supplier` tool call 记录
- supplier scorecard evidence

### Graph 主链路更新

更新 `backend/app/agents/graphs/workflows/product_launch.py`：

原链路：

```text
product_research -> profit_analysis -> listing_validation
```

新链路：

```text
product_research -> profit_analysis -> supplier_evaluation -> listing_validation
```

同时更新 `STEP_AGENT_ROLES`：

- `supplier_evaluation` -> Supplier Agent

因此 trace 中的供应商节点不会被错误归类到 Supervisor 或 Listing Agent。

### Risk Review 更新

更新 `risk_review_node`：

- 当 `supplier_risk_level == "high"` 时，将 overall risk 提升为 high。
- 审批原因追加 `supplier_risk`。
- `publish_listing` 仍始终保留为发布动作审批原因。

### Node Contract 更新

更新 `backend/app/agents/graphs/nodes/base.py`：

`supplier_evaluation` contract 现在声明输出：

- `tool_calls`
- `evidence`
- `supplier_evaluations`
- `selected_supplier_id`
- `supplier_risk_level`

## API 更新

更新 `POST /workflows` 响应：

- `supplier_evaluations`
- `selected_supplier_id`
- `supplier_risk_level`

这样前端或调试页面可以直接展示供应商评估结果。

## 测试覆盖

更新：

- `backend/tests/test_product_launch_graph.py`
- `backend/tests/test_workflows_api.py`
- `backend/tests/test_langgraph_contract.py`

覆盖场景：

- graph 完成步骤中包含 `supplier_evaluation`。
- `supplier_evaluation` 位于 `profit_analysis` 和 `listing_validation` 之间。
- 默认流程选中 `SUP-1`，供应商风险为 low。
- tool calls 中记录 `score_supplier`。
- 高供应商风险时 Risk Review 追加 `supplier_risk`。
- trace 中 `supplier_evaluation` 属于 Supplier Agent。
- API 响应返回供应商评估字段。
- node contract 声明供应商节点关键输出。

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

- 后端测试累计 `70 passed`。

## 重要取舍

- 当前供应商数据是 deterministic mock candidates，不接真实 1688、Alibaba、ERP 或 CSV。
- Supplier Agent 只做评分和风险判断，不执行采购、下单、付款等高风险动作。
- 供应商风险由 Risk Review 统一转化为审批原因，避免 Supplier Agent 自己决定工作流分支。
- `risk_preference="supplier_risk"` 是测试用的确定性场景开关，后续接真实输入时应改为用户传入供应商候选或导入数据。

## 下一节点建议

节点 14：Localization Agent 接入 Listing 主链路。

建议范围：

- 在 Listing validation 前加入 `localization` 节点。
- 增加 locale / target market state。
- 为不同平台生成本地化字段或 locale-specific copy。
- Risk Review 检查本地化后的违规声明。
- trace、snapshot、API 均暴露 localization 输出。
