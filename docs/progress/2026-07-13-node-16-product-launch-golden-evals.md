# Node 16：Product Launch 黄金场景与回放评估

日期：2026-07-13
分支：`codex/node-16-product-launch-golden-evals`
基线：`106544d`

## 目标

本节点把现有确定性 Product Launch 主链路固化为 7 个版本化黄金场景。评估运行器复用 preview、snapshot resume 和 publish node，不调用真实模型、marketplace API 或数据库；运行结果可直接用于 CI 回归门禁。

## 场景目录

| 场景 | 动作 | 核心结果 |
|---|---|---|
| `three-platform-approved-publish` | `approve_and_resume` | 三平台发布完成，3 条 validation、6 个 listing version、3 个稳定发布 ID |
| `low-profit` | `preview` | `awaiting_approval`，利润与总体风险为 high |
| `high-risk-supplier` | `preview` | supplier high，不选择供应商，审批原因包含 `supplier_risk` |
| `localization-claim` | `preview` | 1 条本地化风险，Shopify validation 仍为 true |
| `missing-approval` | `remove_approval_then_publish` | workflow failed，错误类别为 `approval request not found`，零发布 |
| `tampered-version-hash` | `tamper_approval_hash_then_resume` | workflow failed，adapter 调用前拒绝审批 hash 篡改 |
| `adapter-validation-failure` | `approve_and_resume` | workflow failed，版本进入 `publish_failed`，记录 1 条 failed publish trace |

场景 JSON 固定 tenant、workflow、输入、动作和版本；expected JSON 显式保存完整摘要 hash、listing version ID/hash、发布 ID、trace 计数和错误类别。runner 不从 actual 动态生成 expected。

## 结果契约

- `EvaluationResult` 使用 `evaluation-result/v1`，顶层与摘要均包含非空 `tenant_id`、`workflow_id`，且两层身份必须一致。
- 空字符串和纯空白身份均拒绝；分数限制在 `[0, 1]`。
- `ProductLaunchEvaluationSummary` 只保留身份、终态、风险、供应商 ID、审批/快照 ID、validation 摘要、listing version ID/hash/stage、发布摘要、错误类别和 trace 计数。
- 结果不保存完整 listing、message、evidence、approval request 或 draft payload。
- `canonical_summary_hash` 对排序后的紧凑 JSON 计算 SHA-256，重复回放得到相同摘要和结果 ID。
- 固定 8 项 metric：identity、state/risk、approval/snapshot、listing version、validation、publish、trace、error；每项阈值均为 `1.0`。
- 回归门禁 fail closed：空结果、failed result、总分低于 `1.0`、非 `1.0` 阈值或任一 metric 未通过都会抛出 `EvaluationGateError`。

## 仓储隔离

每次场景回放创建新的 `ApprovalRepository`、`WorkflowSnapshotRepository` 和 `TraceEventRepository`。进程级 `RLock` 保护 getter override context，同时替换 workflow 的三个 getter 与 listing node 的 approval getter，并在 `finally` 恢复原绑定。

测试分别在成功和强制异常路径中向三个全局仓储写入 sentinel，确认内容与 getter 绑定在回放前后完全不变。编排异常统一转成 `workflow_exception:<ExceptionType>`，不保存异常消息正文。

## TDD 证据

- Task 1 RED：测试收集因 `app.agents.evaluation.results` 不存在而失败；GREEN 为 2 项结果契约测试通过。
- Task 2 RED：测试收集因 `app.agents.evaluation.runner` 不存在而失败；GREEN 覆盖 7 对排序夹具、畸形 JSON、未知字段、空/重复平台、非法价格、孤儿文件、重复和不一致身份。
- Task 3 RED：缺少 `run_product_launch_scenario`；GREEN 覆盖七场景结果、确定性重放、禁网和异常归一化。
- Task 4 RED：缺少 `EvaluationGateError`；GREEN 覆盖成功/异常仓储隔离与 status/metric/score 回归。
- 评审修复 RED：纯空白 tenant 与空结果门禁未报错；GREEN 后增加顶层/摘要身份一致性与 fail-closed 空门禁。

## 测试与质量门禁

固定解释器：`C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`

- 开发前完整 backend baseline：`83 passed in 1.96s`。
- 最终节点聚焦测试：`24 passed in 1.22s`。
- 黄金评估 + graph + snapshot + trace + 工程契约：`59 passed in 1.49s`。
- 最终完整 backend：`107 passed in 2.00s`。
- `python -m compileall -q app tests`：通过。
- `git diff --check`：通过。
- 结果 payload 审计：7 个结果全部通过门禁，禁用完整 payload key 命中数为 0。

## 代码评审

结构化 branch-diff 自查发现并修复 2 个 Important 边界问题：纯空白 tenant 可绕过非空校验、空结果集合可让门禁真空通过。修复后重新执行聚焦、联合和完整测试。

已通过本机 Codex CLI 的只读 `review --base 106544d` 两次请求独立评审，但 reviewer 均因服务端 `429 Too Many Requests` 中断；只读备用 reviewer 也因认证 `401` 失败。三个请求都未返回 findings，因此不能宣称独立评审通过。当前结构化 branch-diff 自查没有未解决的 Critical/Important，该外部评审缺口作为已知风险保留。

## Node 20 边界

本节点不持久化 `EvaluationResult`、不新增 API、不修改 workflow/repository/registry/公共路由，也不接真实外部服务。Node 20 只消费 `run_product_launch_suite()` 的内存结果并决定公共接线；不会重写场景执行、摘要比较或回归门禁逻辑。
