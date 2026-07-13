# 节点 19：客服 Routed RAG 证据基线

日期：2026-07-13
分支：`codex/node-19-support-rag`
基线：`106544d`

## 目标与范围

本节点实现客服 Routed RAG baseline：实时订单、物流、支付、退款金额、库存、优惠券和历史工单问题只返回结构化工具需求；静态商品与政策问题经过 tenant/ACL 预过滤、词法检索、安全过滤和上下文装配后生成可编辑草稿及真实引用。

本节点没有修改公共 API、Agent profile、共享 graph state 或工具 registry，没有调用真实模型、向量库、reranker、平台 API 和外部服务。没有新增 evaluator/refiner loop。

## 契约与端口

- 新增冻结且 `extra="forbid"` 的 Pydantic 契约，覆盖 source、chunk、locator、request、planner decision、retrieval、context、citation、response 和 privacy-safe trace summary。
- locator 必须包含绝对 URI 及真实 page、section、row 或 timestamp 位置；拒绝 page 0、伪 URI、无定位信息和无时区 datetime。
- source/chunk 保留 tenant、ACL、marketplace、locale、product、policy version、authority、effective time、content hash、index version 和 parent ID。
- `SupportIngestionPort`、`SupportRetriever`、`SupportPlanner` 为后续持久化索引和 Node 20 接线保留替换边界。

## 摄取生命周期

- 内存索引以 `(tenant_id, source_id)` 管理 active source，同一完整版本幂等跳过，新版本在整批校验成功后原子替换。
- chunk 文本 SHA-256、租户、source、index version、业务 metadata 和 ACL 在写入前校验；chunk ACL 不得弱于 source ACL。
- ACL metadata 发生变化时，即使 content hash/index version 未变也会更新，避免权限收紧被幂等短路。
- 同租户跨 source 的 chunk ID 冲突返回稳定失败，不覆盖现有 chunk。
- 版本替换和 source tombstone 同步移除 postings；重复 tombstone 幂等跳过，跨租户同名 source 不受影响。

## 路由矩阵

| 问题类型 | route | 行为 |
| --- | --- | --- |
| 订单状态、物流轨迹、支付状态、退款金额、库存、优惠券、历史工单 | `requires_transaction_tool` | 只返回 `TransactionToolRequest`，不执行工具 |
| 退款政策、物流 SLA、商品事实及其他静态知识 | `lexical_retrieval` | 单次 ACL 预过滤词法检索并生成引用草稿 |
| 天气等离题内容 | `off_topic` | 受控拒绝，不检索 |
| 法律威胁 | `escalate` | 升级人工，不检索 |

`refund policy` 规则优先于 refund amount 交易词，避免政策问题误走实时工具。Planner 只生成 intent、route、filters、reason 和工具需求，不读取工具 registry。

## ACL、过期与注入防线

- tenant、actor scopes、marketplace、locale、product 和 effective time 先形成允许 ID 集合，评分器只接触集合内 chunk 文本。
- postings 在摄取时构建，请求时不重建全量词法索引。
- 过期计数只统计达到查询词法阈值的过期候选，避免无关历史文档污染普通无答案判断。
- ACL 拒绝与空 corpus 的对外响应完全一致；过期证据返回 `stale_evidence`；索引不可用返回 `escalated/retrieval_unavailable`。
- 检索文档按不可信数据处理；命中 route/filter/tool/ACL/伪引用注入模式的 chunk 在 context 装配前移除，安全相邻证据可以继续使用。
- context 最多 5 个 chunk/4000 字符，按 source/parent/规范化文本哈希去重；evidence block 与 citation 一一对应并保留原 locator。
- trace 只记录 trace/tenant/source ID、index version、数量、分数、决策和错误类别，不记录 query、chunk 正文或完整响应。

## 安全评估基线

`backend/evals/support/v1/cases.json` 固定 10 个 case：商品事实、当前退货政策、marketplace 隔离、交易路由、无答案、离题、同租户 ACL 拒绝、跨租户拒绝、过期政策和 prompt injection。

确定性评估结果：

- permission leak rate：`0.0`
- citation precision：`1.0`
- no-answer accuracy：`1.0`
- prompt-injection success rate：`0.0`
- failed case IDs：空

评估不使用 LLM judge，也不调用真实外部服务。

## PRD 与架构对照

- PRD 7.11：本节点输出可编辑 draft，不执行发送；政策和商品回答带引用；实时交易事实不从静态知识编造，退款/补偿动作没有执行入口。
- PRD 15.3：本节点是同步、确定性、单次检索的领域 baseline，不接 API job queue 或持久化 step state；长任务异步执行仍由后续公共运行时节点负责。
- 共享 Node 16-19 设计：保持 Routed RAG 成熟度，不增加 Agentic loop；未修改冻结公共文件。
- Node 20 边界：注册 Support API、连接 Node 18 交易事实 port 与 `requires_transaction_tool`，并决定公共鉴权/异步执行接线。本节点不提前实现这些集成。

## TDD 与验证

- 基线：主线程在隔离 worktree 验证 `83 passed`。
- 每项实现均先运行计划聚焦命令观察预期 RED，再写最小 GREEN。
- Node 19 聚焦：`python -m pytest tests/test_support_rag.py -v`，`47 passed`。
- 完整 backend：`python -m pytest -v`，`130 passed`。
- 编译检查：`python -m compileall -q app tests`，退出码 `0`。
- 差异检查：仓库根目录 `git diff --check`，退出码 `0`。

## 审查结论与剩余限制

对照共享设计、PRD 7.11/15.3 以及 production RAG security/evaluation 清单完成 branch diff 自查，修复了 ACL 更新被幂等短路、跨 source chunk ID 覆盖和低分过期误判三项重要问题，未发现剩余 Critical/Important 代码问题。

当前 Worker 环境没有可用的独立子 Agent/评审工具，无法完成真正独立的第二评审；已用完整写集合审查、TDD 回归、全量测试和确定性安全门禁补充验证。内存索引、规则 Planner、词法 tokenization 和模式式注入过滤仍是 baseline 实现，不代表真实持久化、多语言语义召回或完整生产防护。
