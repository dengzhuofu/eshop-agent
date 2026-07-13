# Node 16-19 并行开发设计

日期：2026-07-13
状态：Approved for implementation

## 1. 设计目标

在不破坏 Node 15 已稳定的 Product Launch 主链路前提下，并行补齐四类能力：可回放评估、统一工具执行边界、发布后运营监控、客服知识检索。设计遵循 PRD 的“选品到复盘”全链路，并以 Agent Harness 的显式状态、受控工具、租户隔离、审批、审计和可重复验证为约束。

本批次采用“独立能力分支 + 单一集成节点”。四个实现 Agent 不修改同一组公共文件；公共注册、跨模块连接和 API 汇总在所有分支通过评审后统一完成。

## 2. 方案选择

已比较三种路径：

- 四节点并行：同时建设质量底座、执行底座、运营链路和客服链路，作品集与工程性同步增长。
- 可靠性串行优先：先完成 ToolExecutor 和 durable runtime，风险最低但业务闭环出现较慢。
- 业务演示优先：先做 Ops 与客服界面，演示快但继续保留节点直接调用 adapter 的结构债务。

采用第一种方案。用户目标明确要求多 Agent 并发，且四个节点可以通过文件所有权和接口冻结实现低冲突并行。

## 3. 并行工作流

### Node 16：Product Launch 黄金场景与回放评估

职责：把当前确定性主链路变成版本化、可回放、可比较的质量基线。

拥有目录：

```text
backend/evals/product_launch/
backend/app/agents/evaluation/runner.py
backend/app/agents/evaluation/results.py
backend/tests/test_product_launch_golden.py
docs/progress/2026-07-13-node-16-product-launch-golden-evals.md
```

必须覆盖三平台正常发布、低利润、高风险供应商、本地化违规声明、审批缺失、版本哈希篡改和 adapter 校验失败。场景固定输入、预期状态、关键 trace、审批和 listing version，不调用真实模型。

### Node 17：Typed Tool Contract 与 ToolExecutor v1

职责：让工具 registry 从元数据登记表升级为可执行的统一边界。

拥有目录：

```text
backend/app/tools/schemas.py
backend/app/tools/executor.py
backend/app/tools/catalog/
backend/app/tools/registry.py
backend/tests/test_tool_executor.py
docs/progress/2026-07-13-node-17-tool-executor.md
```

ToolExecutor 负责 schema 校验、AgentBoundaryPolicy、tenant/permission/approval、timeout、retry、幂等键、错误规范化和 attempt trace。第一版执行确定性低风险 handler，并为高风险副作用预留 approval proof；不在本分支迁移 Product Launch 节点，避免和其他并行工作争用。

### Node 18：多平台运营读模型与 Ops Agent

职责：补齐模拟铺货后的订单、库存、物流和运营指标链路。

拥有目录：

```text
backend/app/domain/operations.py
backend/app/adapters/operations.py
backend/app/mock_data/operations/
backend/app/services/operations.py
backend/app/agents/graphs/operations/
backend/tests/test_operations_agent.py
docs/progress/2026-07-13-node-18-operations-agent.md
```

第一版只提供 tenant-scoped 只读 port 和 seeded mock，不执行改价、补货或退款。Agent 识别低库存、物流延迟、转化下降和退货上升，输出带证据的 action proposal；写操作仅声明风险和审批要求。

### Node 19：客服 Routed RAG 证据基线

职责：实现“实时交易事实走业务工具，静态政策和商品知识走 RAG”的客服回答基础链路。

拥有目录：

```text
backend/app/domain/support.py
backend/app/rag/support/
backend/app/mock_data/support_kb/
backend/evals/support/
backend/tests/test_support_rag.py
docs/progress/2026-07-13-node-19-support-rag.md
```

采用 Routed RAG，而不是先上 evaluator/refiner 循环。Planner 仅负责意图、route、filter 和拒绝/升级；订单状态、物流轨迹、退款金额和库存状态返回 `requires_transaction_tool`。政策、商品 FAQ、退换货和物流时效说明使用可引用检索。

## 4. 共享接口冻结

并行期间禁止四个分支修改：

```text
backend/app/main.py
backend/app/agents/profiles.py
backend/app/agents/graphs/state.py
backend/app/api/routes/__init__.py
```

Node 17 独占 `backend/app/tools/registry.py`。其他节点只能依赖现有公开接口或在自己的目录定义 port/protocol。公共枚举不得在并行分支新增；各领域使用自己的 Pydantic 模型和受控 Literal 类型，集成时再判断是否提升为共享枚举。

## 5. 数据与调用边界

```text
Product Launch snapshot/trace -> Node 16 scenario runner -> EvaluationResult
Agent node -> Node 17 ToolExecutor -> boundary/schema/retry -> handler -> ToolResult/trace
seeded marketplace events -> Node 18 read port -> Ops graph -> evidence/action proposals
support request -> Node 19 planner -> transaction_tool route 或 ACL retrieval -> cited draft/escalation
```

所有状态和结果都必须包含 `tenant_id`。任何候选文本、订单或运营记录在进入 Agent 上下文前完成 tenant/ACL 过滤。完整 payload 不写入 trace；trace 保存 ID、版本、计数、分数、耗时、决策和错误类别。

## 6. 客服 RAG 生产约束

- 成熟度固定为 Routed RAG baseline；只有评估证明可重复检索失败时才新增 Agentic loop。
- Source/Chunk 必须保留 tenant、permission scopes、marketplace、locale、policy version、authority、content hash、index version 和真实 locator。
- 摄取按 content hash 幂等，支持版本替换和 tombstone；MVP 使用内存索引，但接口必须支持未来 pgvector/Qdrant。
- tenant 和 ACL 在候选内容返回前过滤，父文档扩展也不得越权。
- 检索内容视为不可信输入，不得改变工具、过滤器或安全策略。
- 无证据时返回 insufficient evidence 并升级人工，禁止编造订单、物流、退款或政策。
- 默认评估覆盖事实命中、无答案、离题、权限拒绝、过期政策和文档 prompt injection。
- 质量门禁：保护集 permission leak 为 0；citation precision 目标不低于 0.95；no-answer accuracy 目标不低于 0.90。

## 7. 错误与恢复

- 所有模块边界使用 Pydantic 类型校验，错误转为结构化 failure，不向 API 泄漏未处理异常。
- ToolExecutor 只重试明确标记的 transient error；永久错误、权限错误和 schema 错误不重试。
- 副作用工具必须携带稳定幂等键，重试不得制造重复动作。
- Ops 输入支持 event id 去重，并显式处理迟到、乱序和数据新鲜度。
- RAG 检索为空、索引不可用或证据不足时走降级/升级，不直接让模型自由回答。

## 8. 测试与质量门禁

每个节点必须遵循 TDD，默认测试不得调用真实 SiliconFlow、向量库或平台 API。每个分支完成后需要：

- 节点聚焦测试通过。
- 完整 backend 测试通过。
- `git diff --check` 通过。
- 独立代码评审没有未解决的 Critical/Important。
- 新增中文进度日志和中文 Git 提交描述。

四分支合并后再执行一次全量测试和跨模块集成测试。

## 9. 后续集成节点

Node 20 仅负责公共接线：注册 Ops/Support API，连接 Node 18 交易事实 port 与 Node 19 `requires_transaction_tool` 路由，选择性迁移 Product Launch 的低风险调用到 Node 17 ToolExecutor，并把 Node 16 评估结果暴露给 workflow detail。Node 20 不重写四个节点内部逻辑。

durable checkpointer、可信 RequestContext、真实 SiliconFlow provider 和持久数据库仍是后续 P0/P1；本批次通过 port、typed contract 和评估基线为它们预留边界，不假装已经生产化完成。
