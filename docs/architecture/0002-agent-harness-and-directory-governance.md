# ADR 0002：Agent Harness 范式与目录治理

日期：2026-07-13  
状态：Accepted

## 背景

项目已经完成 Product Launch 主链路的多个节点，并具备 `agents/graphs`、`tools`、`adapters`、`security`、`observability`、`checkpoints`、`prompts`、`skills`、`memory`、`evaluation` 等基础目录。

用户进一步要求：开发不仅要沿 PRD 推进，还要持续判断 PRD 链路是否合理；要并行使用 agent 提升效率，但不能牺牲质量；还要检查当前 Agent 开发是否符合主流范式、目录结构是否符合主流 Agent 工程规范，并符合 agent harness 思想。

本 ADR 固化后续开发的治理原则，避免项目变成“节点不断堆进单文件”的 demo，也避免为了显得专业而过早引入真实外部依赖。

## 结论

### 0. 主流 LangGraph / Agent Harness 对照

根据 LangGraph 官方文档，LangGraph 的定位是长运行、有状态 agent 的低层编排 runtime，核心能力包括 durable execution、streaming、human-in-the-loop、persistence 和 observability。官方 persistence 文档还区分了 checkpointer 与 store：checkpointer 负责 thread-scoped graph state，store 负责跨 thread 的长期应用数据。HITL interrupt 文档使用 `interrupt()`、`Command(resume=...)`、`thread_id` 作为主流恢复方式。

参考：

- https://docs.langchain.com/oss/python/langgraph/overview
- https://docs.langchain.com/oss/python/langgraph/persistence
- https://docs.langchain.com/oss/python/langgraph/interrupts
- https://docs.langchain.com/oss/python/langgraph/streaming

因此，本项目当前的自定义 snapshot / approval resume 是 MVP 过渡方案：它能展示可恢复与审批边界，但还不能等同于完整 LangGraph checkpointer + interrupt runtime。后续进入生产化节点时，需要明确是否迁移到 `compile(checkpointer=...)`、`thread_id`、`interrupt()` 和 `Command(resume=...)`。

### 1. 本项目采用的 Agent Harness 思想

这里的 agent harness 不是单一框架名，而是一组工程约束：

- workflow 是可编排状态机，而不是一次性 chat completion。
- agent 通过受控 tool、adapter、service 行动，而不是直接访问外部系统。
- 每个 agent 有 profile、允许工具、风险边界、禁止上下文。
- LangGraph node 只产出显式 state update，不隐藏 route 决策。
- route 只做确定性分支选择，不调用工具、不写存储、不执行副作用。
- 高风险动作必须经过 checkpoint / approval interrupt。
- 每个关键节点输出都能进入 trace、snapshot、API 或 evaluation。
- workflow 能从 checkpoint 恢复，发布类操作具备幂等语义。
- prompt、tool、skill、memory、evaluation 需要版本化或 registry 化，便于回归和审计。
- mock adapter / mock data 是 MVP 的生产替身，必须保留未来真实 connector 的边界。

### 2. 当前符合主流范式的部分

- `backend/app/agents/graphs/` 已按 `state`、`nodes`、`routes`、`workflows` 拆分。
- `backend/app/tools/registry.py` 已记录 tool risk、permission、approval、idempotency metadata。
- `backend/app/security/` 已实现跨租户、权限、审批、secret-like payload 拦截测试。
- `backend/app/adapters/` 已隔离 marketplace adapter 和 mock marketplace 规则。
- `backend/app/agents/profiles.py` 已定义 agent role、工具白名单、风险边界、禁用数据类别。
- `backend/app/agents/checkpoints`、`prompts`、`memory`、`evaluation`、`skills`、`mcp` 已有 metadata-first 骨架。
- `backend/app/repositories` 已提供 approval、snapshot、trace event 的内存实现，便于 MVP 可回放。
- `backend/tests` 覆盖了 agent boundary、LangGraph contract、approval、snapshot、trace、security isolation 和 product launch workflow。
- `docs/progress/` 和 `docs/superpowers/plans/` 记录每个节点的实现与验证，利于上下文压缩和作品集讲解。

### 3. 当前主要短板

- `backend/app/agents/graphs/nodes/product_launch.py` 已开始膨胀，集中放入 research、profit、supplier、listing、localization、risk、approval、publish 等多个节点及 helper。
- `backend/app/agents/graphs/workflows/product_launch.py` 同时承担 graph build、执行入口、trace event 写入、snapshot 保存和 resume 编排。
- mock supplier、listing draft、本地化规则仍硬编码在 node 文件中，后续会影响 golden scenario 和 demo replay。
- `prompts`、`evaluation`、`memory`、`checkpoints` 当前更多是 metadata registry，尚未全部驱动真实执行路径。
- tool registry 尚未拆分 input/output schema、tool version、executor 层；MVP 可接受，但后续工具数量增加会变重。
- FastAPI route 仍承担 demo tenant、workflow id 生成、响应拼装；后续应下沉到 application/use case 层。
- repository 目前是内存单例，适合 MVP；接数据库前需要 protocol/interface，避免 graph/API 直接绑定内存实现。
- 目前没有使用 LangGraph 原生 checkpointer、store、interrupt 和 stream events；这会限制长任务、实时进度、HITL 恢复和失败重放能力。
- tool registry 还没有成为所有工具调用的统一 executor，profit / supplier / validation / localization 等仍然是 node 直接调用服务或 adapter。
- `ToolDefinition` 仍缺少 PRD 要求的 input schema、output schema、timeout、retry、audit policy、tool version 等字段。
- trace 当前是运行后补记 event，不是 runtime span；缺 node_start、latency、token/cost、retry attempt、tool version、prompt version 等生产观测字段。
- evaluation 当前是 scenario registry，不是质量门禁；还没有 golden scenario runner 或 EvaluationResult repository。
- 当前 risk route 只有 approval / complete，缺少 retry / fail / escalation；且发布类 workflow 当前必然需要 approval，`complete` 分支主要是占位。

## 后续治理规则

### Rule 1：新增节点前先判断是否真的需要 Agent Node

只有满足以下条件时才新增 LangGraph node：

- 有明确业务阶段和 agent owner。
- 输入/输出需要进入 workflow state。
- 输出会影响后续 route、approval、trace、snapshot、evaluation 或用户可见结果。
- 有可测试的 deterministic skeleton。

否则优先实现为 service、tool、adapter 或 evaluation helper。

### Rule 2：节点文件按领域拆分

从 Node 15 开始，不再继续向 `nodes/product_launch.py` 追加大块逻辑。

建议目标结构：

```text
backend/app/agents/graphs/nodes/
  product_research.py
  profit.py
  suppliers.py
  listings.py
  localization.py
  risk.py
  approval.py
  publishing.py
  base.py
```

如果一次性拆分风险过高，可以按新增节点顺手拆相关领域。

### Rule 3：workflow 文件只保留编排，副作用记录逐步外移

`workflows/product_launch.py` 后续应拆出：

```text
backend/app/agents/graphs/workflows/product_launch.py
backend/app/agents/graphs/workflows/product_launch_executor.py
backend/app/agents/observability/recorders.py
backend/app/agents/checkpoints/service.py
```

MVP 当前不强制一次完成，但新增 trace/checkpoint 行为时优先放到 recorder/service，而不是继续塞进 workflow builder。

### Rule 3.1：LangGraph durable execution 迁移需要单独 ADR

在引入真实异步 worker、长任务或多轮人工审批前，必须新增 ADR，回答：

- 是否采用 LangGraph checkpointer / store。
- `workflow_id` 与 `thread_id` 的映射规则。
- approval pause 使用业务 approval repo，还是使用 `interrupt()`。
- resume 使用当前双图 publish resume，还是使用 `Command(resume=...)`。
- side effect 在 interrupt 前后如何保证幂等。
- stream events 如何驱动 UI timeline。

在该 ADR 完成前，当前业务 snapshot 方案继续作为 MVP 过渡。

### Rule 4：mock data 与业务规则不要长期硬编码在 node 中

后续将 mock data / deterministic rule 迁到：

```text
backend/app/mock_data/
backend/app/services/
backend/evals/product_launch/
```

节点只做编排和 state update；计算、评分、规则、mock 样本由 service 或 fixture 提供。

### Rule 5：评估体系要从 registry 进入可运行 artifact

下一阶段至少建立：

```text
backend/evals/product_launch/
  scenarios/*.json
  expected/*.json
```

先用 pytest 驱动 golden scenario，不急着接复杂 LLM-as-judge。

### Rule 7：所有工具调用逐步收敛到 ToolExecutor

后续新增真实外部系统前，建立统一 `ToolExecutor`：

```text
backend/app/tools/
  registry.py
  executor.py
  schemas.py
  catalog/
```

ToolExecutor 负责：

- agent profile / tool whitelist 检查
- tenant / permission / approval 检查
- input / output schema validate
- idempotency key
- timeout / retry policy
- audit / trace event
- error normalization

节点不应长期直接调用真实外部 adapter 或高风险 service。

### Rule 6：文档和日志必须服务恢复与审查

- 每个完成节点继续写 `docs/progress/`。
- 重大架构治理写 ADR。
- 计划文件放 `docs/superpowers/plans/`。
- 避免把本地运行产物、secret、完整大 payload 写入文档和 trace。

## 优先级路线

### P0：随 Node 14 完成

- Localization Agent 接入主链路。
- 补齐 trace/API/snapshot 可见性。
- 记录本 ADR 作为 agent harness 和目录治理基线。

### P1：Node 15 建议

Listing 草稿版本化与发布 payload 对齐：

- 把 `listing_drafts` / `localized_listings` 抽象为 listing version 结构。
- approval metadata 展示发布 diff 摘要。
- publish result 关联 listing version。
- 为 Listing Workspace 和 Approval Center UI 打基础。
- 顺手把 listing/localization 相关 helper 从 `product_launch.py` 拆出。

### P2：Node 16-17 建议

- 建立 product launch golden scenario fixtures。
- 拆出 trace recorder 和 checkpoint service。
- 把 mock supplier/listing/localization 数据迁出 node 文件。
- 新增 ToolExecutor skeleton，并让低风险 deterministic tools 先接入。
- 新增 State / Trace / ToolCall contract v1，逐步收紧 `tool_calls: list[dict]`。
- 新增 LangGraph durable execution / HITL ADR。

### P3：后续延后

- 真实 marketplace API / MCP connector。
- PostgreSQL / Redis / Celery / migration 体系。
- 复杂 RAG/vector memory。
- 完整 OpenTelemetry / LangSmith dashboard。
- 大规模多 workflow 拆分。

## 检查清单

后续每个节点完成前，除了功能测试，还要回答：

1. 这个节点是否遵守 agent profile/tool boundary？
2. state 是否只保存恢复和后续执行必要的信息？
3. route 是否仍然纯决策、无副作用？
4. 高风险动作是否必须经过 approval/checkpoint？
5. trace 是否有足够摘要，且没有 secret 或不必要的大 payload？
6. snapshot 是否能支持 resume，不依赖 approval metadata 重建业务状态？
7. 失败是否变成可见 workflow failed/error，而不是未处理异常？
8. 测试是否覆盖 red/green 行为、边界和回归风险？
9. 新逻辑是否让现有大文件继续膨胀？如果是，是否需要顺手拆分？
10. 是否更新 progress log 或 ADR？
