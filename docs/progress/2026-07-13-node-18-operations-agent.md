# Node 18 多平台运营读模型与 Ops Agent 进度

日期：2026-07-13  
分支：`codex/node-18-operations-agent`  
基线：`106544d`

## 1. 所有权与范围

本节点只修改 operations domain、只读 adapter、seeded mock data、service、独立 graph、对应测试、实施计划和本进度日志。未修改 `main.py`、公共 agent profile/state/route、tool registry、API 或其他并行节点文件。

首版范围固定为订单、库存、物流、转化率和退货率的可回放读取与异常建议。PRD 7.10 中曝光、点击、评论评分、客服工单量等后续指标未在本节点扩项。

## 2. 领域与版本关联

- 四类事件均使用 `extra="forbid"`，时间字段必须为 aware datetime。
- 每条事件携带 `tenant_id`、`listing_id`、`listing_version_id`、64 位小写 `listing_content_hash` 和 `sku`。
- summary、evidence、anomaly、proposal 和 failure 均保留租户；证据、异常和建议保留来源 event ID 与 Listing 版本身份。
- proposal 在类型层固定为 `status="proposed"`、`execution_allowed=False`、`RiskLevel.HIGH`、`approval_required_for_execution=True`。

## 3. 读取、去重与新鲜度

- Seeded adapter 先按租户过滤，再应用 marketplace 与 Listing version 过滤；四个 JSON 文件提供 tenant-a 异常场景和 tenant-b 健康对照。
- service 在聚合前重新验证 port 返回值与租户，拒绝跨租户记录、相同 event ID 的冲突 payload 和 Listing version 身份漂移。
- 完全相同的 event ID/payload 幂等去重；冲突 event ID 转为结构化 `event_conflict`。
- `as_of` 由调用方显式传入。未来观察或未来到达记录不进入回放截面。
- 新鲜度上限为订单 86400 秒、库存/物流 21600 秒、指标 172800 秒；迟到阈值为 43200 秒。
- latest 选择使用 `(observed_at, received_at, event_id)`。指标窗口保留基线与当前值，乱序诊断跨窗口按指标流比较。
- 只有 fresh records 可以生成异常、证据和 proposal；全空或全 stale 返回 `insufficient_data`。

## 4. 汇总、异常与建议

- 表现汇总包含订单数、销量、收入、最新库存、最新转化率和退货率，并关联来源事件和 Listing 版本。
- 异常覆盖低库存、至少 24 小时物流延迟、至少 20% 相对转化下降和至少 0.03 绝对退货率上升。
- 零转化基线不会除零或误报相对下降；阈值等号按命中处理；tenant-b 健康对照不产生异常。
- 建议映射为补货审查、客服策略审查、价格审查和 Listing 优化审查，只声明风险与审批要求，不执行任何写操作。

## 5. Graph 与 trace

独立 StateGraph 流程为：

```text
START -> load_operations -> route -> detect_anomalies -> propose_actions -> complete -> END
```

失败或数据不足路径为 `load_operations -> route -> complete`。route 只读取 state 并返回确定性分支；节点只返回显式 state update，不导入写 adapter、approval repository 或 executor。

trace summary 只保存 workflow/tenant/步骤 ID、来源 event ID、Listing version ID、异常/证据/proposal ID、记录计数、新鲜度、决策和错误码，不保存订单、指标、收入或建议正文 payload。同一 workflow、tenant、`as_of` 和输入可重放出稳定 summary/anomaly/evidence/proposal/trace ID。

## 6. TDD 与验证证据

- Baseline：完整 backend `83 passed in 1.20s`。
- Task 1 RED：缺少 `app.domain.operations`；GREEN：领域聚焦 `2 passed`。
- Task 2 RED：缺少 `app.adapters.operations`；GREEN：adapter 聚焦 `2 passed`，当时完整节点文件 `4 passed`。
- Task 3 RED：缺少 `app.services.operations`；GREEN：service 聚焦 `9 passed`，当时完整节点文件 `12 passed`。
- Task 4 RED：缺少 operations graph；GREEN：graph/trace/replay 聚焦 `7 passed`，当时完整节点文件 `18 passed`。
- 评审修复 RED：旧指标窗口晚到未标记乱序；GREEN：回归测试通过。
- 最终聚焦：`19 passed in 0.59s`。
- 最终完整 backend：`102 passed in 1.61s`。
- `python -m compileall -q app tests`：exit 0。
- `git diff --check`：exit 0。
- `git diff --name-only 106544d...HEAD`：只包含 Node 18 所有权文件。

计划原比较点 `5cc8bc5` 早于主线基线 `106544d`；该范围会包含 `106544d` 已加入的 Node 16/17/19 计划文件，因此本节点按用户指定基线 `106544d` 审查实际分支写集合。

## 7. 评审结论与剩余边界

已按并行开发设计、PRD 7.10 和 ADR 0002 做逐项 branch-diff 自查。发现并修复一项 Important：指标乱序诊断原先错误地按窗口隔离，现已将乱序键与 latest 选择键拆分。未发现剩余 Critical/Important。

当前执行环境未提供独立 reviewer/subagent 工具，因此无法完成独立 Agent 评审；该项保留为待主线程复核，不伪造评审结果。

Node 20 负责 API、公共注册和跨模块接线。本节点不提供真实平台 connector、数据库、durable checkpointer、审批执行或任何副作用；这些边界均通过 `OperationsReadPort`、结构化 state/failure 和不可执行 proposal 保留。
