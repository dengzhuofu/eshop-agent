# Node 15：刊登草稿版本化与发布 Payload 对齐

日期：2026-07-13
分支：`codex/node-15-listing-versioning`

## 目标

本节点为跨境电商 Product Launch Agent 增加 `listing_versions`，让本地化草稿、平台校验、人工审批、快照恢复、发布结果和 trace 事件可以串到同一个刊登内容版本上。

核心问题是防止“审批的是 A 稿，恢复发布时实际发布了 B 稿”。在跨境电商场景里，标题、价格、平台属性、locale 文案和营销 claim 都可能影响合规与平台审核，因此发布前必须能够证明版本 ID 与内容哈希一致。

## 实现范围

- 新增 `ListingVersion` 领域模型。
- 新增 `backend/app/services/listing_versions.py`：
  - 生成 deterministic `content_hash`
  - 创建稳定 `version_id`
  - 生成审批和 trace 可用的轻量版本摘要
- `CommerceAgentState` 新增：
  - `listing_versions`
  - `selected_listing_version_ids`
  - `approved_listing_version_ids`
- 新增 `backend/app/agents/graphs/nodes/listings.py`，并将 listing/localization/publish 相关节点从 `product_launch.py` 拆出。
- `localization_node` 现在为每个平台生成：
  - base draft version
  - localized selected version
- `listing_validation_node` 将 validation 结果写回对应 `listing_version_id`。
- `await_approval_node` 的 metadata 增加：
  - `listing_version_ids`
  - `listing_version_hashes`
  - `listing_version_summary`
  - `publish_diff_summary`
- `publish_listing_node` 只发布 approval metadata 绑定的版本，并在恢复发布时重新计算 draft hash、校验 deterministic `version_id`、版本归属和审批集合。
- `publish_results` 与 publish tool trace 增加：
  - `listing_version_id`
  - `listing_content_hash`
  - `idempotency_key`
- 多平台部分发布失败时，保留已成功结果和 tool trace，并区分 `published` / `publish_failed` 版本状态。
- workflow create API 拒绝空或重复的平台集合，避免重复幂等键调用和不完整审批。
- workflow trace 的 localization node metadata 增加 compact 版本摘要。
- workflow API create/resume 响应暴露 MVP 调试所需版本字段。

## Agent Harness 对齐

- route 仍然只做分支决策，不执行副作用。
- marketplace adapter 仍只处理 `ListingDraft`，不承担版本治理。
- approval metadata 只保存轻量索引与摘要，不保存完整 listing payload。
- snapshot 保存完整 `listing_versions`，resume 不依赖 approval metadata 重建业务状态。
- publish 是 approval-gated side effect，并使用 `{approval_id}:{listing_version_id}:{marketplace}` 作为幂等键。
- 对实际 draft、snapshot 版本记录和 approval metadata 做三方完整性校验，避免恢复时发布未审批草稿。
- 批准版本集合必须与 snapshot selected 集合严格一致，不能静默少发、换序或夹带版本。
- 失败路径同样记录已经发生的 publish tool event，避免外部副作用脱离审计链。

## 测试与验证

先写失败测试，再实现版本化逻辑。

验证命令：

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_langgraph_contract.py tests/test_product_launch_graph.py tests/test_workflows_api.py -v
```

结果：`37 passed`

完整验证命令：

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest -v
```

结果：`83 passed`

新增/增强的关键测试覆盖：

- 初始 state 与 node contract 包含版本化字段。
- localization 产出 base/localized 两级版本。
- validation 结果关联 `listing_version_id`。
- approval metadata 包含版本 ID、hash 和摘要，且不写完整 draft。
- snapshot 保存 `listing_versions` 与 selected version IDs。
- resume 发布结果回指被审批的 `listing_version_id`。
- publish tool trace 与 publish results 的版本 ID 一致。
- 篡改 approval metadata 中的版本 hash 会导致 workflow failed，不会继续发布。
- 篡改实际 draft 但保留旧 hash、篡改 deterministic version ID、构造畸形版本都会在 adapter 副作用前受控失败。
- 审批版本集合少于 selected 集合时拒绝发布。
- 多平台部分发布失败时保留已成功版本状态、结果和 trace。
- 空或重复 marketplace 输入返回 422。

## 代码评审闭环

评审发现 1 个 Critical、2 个 Important 和 1 个 Minor 问题，均已验证并修复：

- 发布前从实际 draft 重算 canonical hash，并校验 deterministic version ID。
- 对完整 `ListingVersion` 做 Pydantic 解析与 workflow/tenant 归属校验，畸形快照转为受控失败。
- 部分发布失败时记录已发生副作用，并保留批准版本和逐版本 stage。
- 严格校验 approval IDs 与 snapshot selected IDs，API 拒绝空或重复平台。
- publish result 与 tool trace 同时断言精确幂等键格式。
- 将 approval workflow/tenant 作为可信归属，拒绝与 snapshot state 或 listing version 不一致的恢复请求。
- 使用严格 `ListingApprovalIndex` 解析审批版本索引，畸形 metadata 不再导致 500。
- 失败的 publish 尝试也记录版本 ID、hash、marketplace、幂等键和错误状态。

## 后续建议

- Node 16 可继续拆出 trace recorder / checkpoint service，减少 workflow 文件职责。
- 增加 Product Launch golden scenario fixtures，将版本化输出加入回归样例。
- 后续接真实 marketplace connector 前，引入统一 `ToolExecutor`，把 schema validate、retry、timeout、audit、tool version 和 idempotency 收敛到工具执行层。
- Listing Workspace UI 可以直接基于 `listing_versions` 展示版本 diff、审批状态和发布状态。
