# 节点 14：Localization Agent 接入 Listing 主链路

时间：2026-07-13  
实现分支：`codex/node-14-localization-agent`  
状态：已完成

## 本节点目标

- 将 PRD 主链路中的 Localization Agent 接入 Product Launch LangGraph。
- 让本地化结果进入 workflow state、approval snapshot、trace event 和 API 响应。
- 让 Listing validation 校验本地化后的最终草稿，避免本地化文案绕过平台规则。
- 让 Risk Review 能基于本地化风险标记追加审批原因。

## 已完成内容

### State 扩展

更新 `backend/app/agents/graphs/state.py`：

- `target_locale`
- `listing_drafts`
- `localized_listings`
- `localization_risk_flags`

这些字段会随 workflow snapshot 保存，审批通过后的发布恢复不需要从 approval metadata 重建本地化状态。

### Localization Node

更新 `backend/app/agents/graphs/nodes/product_launch.py`：

- 新增 `localization_node`
- MVP 使用 deterministic mock localization，不接真实翻译 API
- `en-GB` 会写入 `unit_style=metric` 和 `market_wording=UK English`
- 默认保留 source draft、locale、changes、risk_flags、localized draft
- `risk_preference="localization_risk"` 会产出高风险本地化声明，用于测试 Risk Review 行为
- `listing_validation_node` 与 `publish_listing_node` 改为优先使用本地化后的 draft

### Graph 主链路更新

更新 `backend/app/agents/graphs/workflows/product_launch.py`：

原链路：

```text
product_research -> profit_analysis -> supplier_evaluation -> listing_validation -> risk_review
```

新链路：

```text
product_research -> profit_analysis -> supplier_evaluation -> localization -> listing_validation -> risk_review
```

同时更新 `STEP_AGENT_ROLES`：

- `localization` -> `AgentRole.LOCALIZATION`

### Trace 归属修正

`_record_tool_call_events` 现在优先读取 tool call 中的 `agent_role`。

这样 preview 阶段的 `localize_listing` tool call 会归属 Localization Agent，而不是因为最终状态停在 Supervisor 就被错误归到 Supervisor。

`localization` node end event 还会写入精简摘要：

- `target_locale`
- `localized_listing_count`
- `localization_risk_count`
- `marketplaces`

不把完整本地化文案塞进 trace，避免 trace payload 过大或暴露不必要内容。

### Risk Review 更新

`risk_review_node` 现在读取 `localization_risk_flags`：

- 出现 high / critical 本地化风险时，整体风险升级为 `high`
- 审批原因追加 `localization_risk`
- `publish_listing` 仍然保留为默认发布审批原因

### Node Contract 更新

更新 `backend/app/agents/graphs/nodes/base.py`：

- 新增 `localization` contract
- 校准旧的 `listing_draft` contract 名称为实际主图节点 `listing_validation`

### API 更新

更新 `backend/app/api/routes/workflows.py`：

- `POST /workflows` 请求支持 `target_locale`
- workflow id hash 纳入 `target_locale`
- create response 返回：
  - `target_locale`
  - `listing_drafts`
  - `localized_listings`
  - `localization_risk_flags`
- resume response 返回 `target_locale`、`listing_drafts`、`localized_listings`、`localization_risk_flags`

### 发布失败处理

审批通过后，如果本地化文案仍然无法通过 adapter 发布校验，`publish_listing_node` 会将 adapter validation failure 转换成 workflow failed state：

- `current_step = failed`
- `errors` 记录明确原因，例如 `Cannot publish invalid listing: claims`
- API resume 返回 409，而不是抛出未处理异常

## 测试覆盖

更新：

- `backend/tests/test_product_launch_graph.py`
- `backend/tests/test_workflows_api.py`
- `backend/tests/test_langgraph_contract.py`

覆盖场景：

- initial state 包含 localization 相关字段
- node contract 包含 Localization Agent 边界
- `localization` 位于 `supplier_evaluation` 与 `listing_validation` 之间
- `localized_listings` 数量与目标平台一致
- `localize_listing` tool call 被记录
- localization trace node 属于 Localization Agent
- `localize_listing` tool call trace 属于 Localization Agent
- 本地化高风险时 Risk Review 追加 `localization_risk`
- 本地化引入 unsupported claim 时，Listing validation 能标记 `claims` issue
- 审批后发布 invalid localized listing 时返回 workflow failed / API 409
- API 响应暴露本地化结果
- publish resume 使用 snapshot 中的本地化状态

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

- 后端测试累计 `74 passed`
- 仍有 pytest cache 写入权限 warning，不影响功能验证

## 重要取舍

- 本节点只做 deterministic localization skeleton，不接真实翻译 API 或 LLM 翻译。
- Localization Agent 不发布 Listing、不改价格、不改库存、不退款，也不决定 route。
- Listing validation 和 publish 统一使用本地化后的草稿，保证最终执行内容经过平台规则校验。
- Risk Review 只读取 localization node 产出的显式风险标记，避免把复杂业务判断藏进 LangGraph route。
- `risk_preference="localization_risk"` 是测试用确定性场景开关，未来真实输入接入后应替换为来自本地化服务或规则评估的风险信号。

## 下一节点建议

节点 15 建议优先做 Listing 草稿版本化与发布 payload 对齐：

- 将 `listing_drafts` / `localized_listings` 抽象成明确的 listing version 结构
- 在 approval metadata 中展示发布 diff 摘要
- 让 publish result 能关联 listing version
- 为后续 Listing Workspace 和 Approval Center UI 打基础
