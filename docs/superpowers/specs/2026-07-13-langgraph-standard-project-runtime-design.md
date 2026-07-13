# 跨境电商 Agent 平台 LangGraph 标准工程与运行时设计

日期：2026-07-13
状态：已确认
适用范围：MVP 目录规范化、LangGraph 原生运行时接入，以及 Node 16-19 合并后的后续开发

## 1. 背景

项目已经具备 Product Launch 主链路、审批、快照、追踪、Listing 版本治理、多平台模拟适配器等能力，并行分支还实现了黄金场景评估、统一 ToolExecutor、Operations Agent 和客服 Routed RAG。

当前主要问题不是缺少业务模块，而是工程结构和运行时边界未完全符合参考项目规范：

- `graph.py` 同时承担图装配、执行、快照、恢复和 trace 写入。
- 当前恢复方式是读取自定义 snapshot 后启动第二张发布图，不是 LangGraph 原生 checkpoint、interrupt 和 resume。
- 缺少稳定 `thread_id`、原生 checkpointer/store、API 依赖注入和 `langgraph.json`。
- `state` 中仍有较多宽泛字典，节点列表没有 reducer，状态版本和恢复兼容规则不明确。
- 模型配置存在，但尚未形成独立的 LLM、Embedding、Reranker provider 层。
- guardrails、persistence、tests 和 evals 目录边界不完整。
- 多个工作流已经出现，继续使用单一平铺 graph 目录会再次形成大文件和交叉依赖。

本设计以所给 LangGraph 示例的模块代码和职责为规范基线，同时针对跨境电商多工作流平台保留必要扩展能力。

## 2. 目标与非目标

### 2.1 目标

1. 后端源码迁移到 `backend/src/app/`，使目录和 Python 工程配置符合示例。
2. 每张业务图均遵守 `graph.py`、`state.py`、`edges.py`、`nodes/` 的明确边界。
3. 使用 LangGraph 1.2.9 原生 checkpointer、store、`interrupt()`、`Command(resume=...)` 和稳定 `thread_id`。
4. 保留 Approval、Trace、发布操作账本等业务事实，不把它们错误地塞进 checkpoint 或 store。
5. API 通过依赖注入获取 graph、认证上下文、仓储和运行时服务。
6. 硅基流动模型访问统一收敛到 `models/`，API key 只从环境变量读取。
7. 客服使用 Routed RAG baseline：静态知识走 ACL 预过滤检索，实时交易事实走工具，无证据时升级人工。
8. 测试分为 unit、contract、integration、e2e，离线质量评估独立放在 `evals/`。
9. MVP 默认内存运行，生产持久化、真实平台连接器和更多工作流可以在既有接口下扩展。

### 2.2 非目标

- 本次不接入真实 Amazon、eBay、TikTok Shop 或支付平台 API。
- 本次不部署 PostgreSQL、Redis、消息队列或向量数据库。
- 本次不把所有确定性节点改成 LLM 节点。
- 本次不为展示复杂度而增加无评估依据的 Agentic RAG 循环。
- 本次不迁移或伪造旧 snapshot 到 LangGraph 内部 checkpoint 表。

## 3. 已确认方案

采用“示例规范核心 + 工作流包”方案。

后端作为独立 Python 工程保留在仓库的 `backend/` 目录中，源码进入 `backend/src/app/`。公共能力严格按照示例模块划分；Product Launch、Operations、Support 等业务图各自拥有标准 graph 结构，并通过 `langgraph.json` 分别导出。

该方案避免两个极端：一是把所有业务塞进单个顶层 graph，二是只增加兼容门面而继续保留旧目录债务。

### 3.1 参考基线

规范来源为：

`C:/Users/Administrator/Documents/Codex/2026-07-13/langgraph-ai/outputs/langgraph-standard-project-code-guide.md`

该文件的 SHA-256 为：

`2e51749b352f76e99f186a2fffd64207528227482cefb6b1a738513d17f84698`

同时参考同目录的 `langgraph-prd-example/langgraph-prd-example/` 示例工程。示例是单图项目，本设计只在“多工作流分别成包”这一点做平台化扩展；每个包内部的 graph、state、edges、nodes 职责以及公共 api、models、persistence、guardrails、tests、evals 规则不降低。

## 4. 目标目录结构

```text
backend/
├── .env.example
├── .gitignore
├── Dockerfile
├── README.md
├── docker-compose.yml
├── langgraph.json
├── pyproject.toml
├── migrations/
├── scripts/
│   └── build_index.py
├── src/
│   └── app/
│       ├── __init__.py
│       ├── configuration.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── app.py
│       │   ├── dependencies.py
│       │   └── routes/
│       ├── adapters/
│       ├── domain/
│       ├── guardrails/
│       │   ├── __init__.py
│       │   ├── input_guard.py
│       │   ├── output_guard.py
│       │   └── retrieved_content_guard.py
│       ├── mock_data/
│       ├── models/
│       │   ├── __init__.py
│       │   ├── embeddings.py
│       │   ├── llm.py
│       │   ├── reranker.py
│       │   ├── vision.py
│       │   └── providers/
│       │       └── siliconflow.py
│       ├── observability/
│       ├── persistence/
│       │   ├── __init__.py
│       │   ├── checkpointer.py
│       │   ├── store.py
│       │   └── repositories/
│       ├── prompts/
│       ├── rag/
│       │   └── support/
│       ├── runtime/
│       │   ├── container.py
│       │   └── context.py
│       ├── schemas/
│       │   ├── api.py
│       │   ├── domain.py
│       │   └── runtime.py
│       ├── services/
│       ├── tools/
│       │   ├── catalog/
│       │   ├── executor.py
│       │   ├── registry.py
│       │   └── schemas.py
│       └── workflows/
│           ├── product_launch/
│           │   ├── __init__.py
│           │   ├── graph.py
│           │   ├── state.py
│           │   ├── edges.py
│           │   └── nodes/
│           ├── operations/
│           │   ├── __init__.py
│           │   ├── graph.py
│           │   ├── state.py
│           │   ├── edges.py
│           │   └── nodes/
│           └── support/
│               ├── __init__.py
│               ├── graph.py
│               ├── state.py
│               ├── edges.py
│               └── nodes/
├── evals/
│   ├── operations/
│   ├── product_launch/
│   ├── support/
│   ├── evaluators/
│   └── run_evals.py
└── tests/
    ├── conftest.py
    ├── unit/
    ├── contract/
    ├── integration/
    └── e2e/

.github/
└── workflows/
    └── backend-ci.yml
```

旧 `backend/app/` 和平铺的 `backend/tests/test_*.py` 只在迁移提交过程中短暂存在，最终不保留两套导入路径或重复实现。
现有 `backend/requirements.txt` 迁移到 `pyproject.toml` 后退役，避免维护两份依赖真源。仓库根目录继续承担全平台说明，`backend/README.md` 只描述后端安装、graph 加载、测试和评估命令。
除数据目录外，每个 Python package 都必须包含 `__init__.py`；目录树为突出职责省略了部分重复的 `__init__.py` 行。

## 5. 模块职责规范

| 模块 | 必须负责 | 禁止负责 |
|---|---|---|
| `graph.py` | 创建 `StateGraph`、注册节点和边、编译并导出模块级 `graph` | 业务计算、仓储写入、API 响应拼装 |
| `state.py` | 可序列化 `TypedDict`、字段类型、reducer、状态版本 | 客户端、连接、secret、仓储实例 |
| `edges.py` | 根据明确 state 字段返回下一节点名称 | 模型调用、工具调用、数据库写入、复杂业务计算 |
| `nodes/` | 单节点单职责，调用 service/tool 并返回状态增量 | 隐藏路由决策、直接获取全局仓储、返回不可序列化对象 |
| `tools/` | 受控副作用和模型可调用能力，统一权限、审批、schema、幂等、重试、审计 | 工作流编排、绕过安全边界直连 provider |
| `services/` | 与 LangGraph 无关的业务逻辑和确定性计算 | 依赖 graph state 或 HTTP 请求对象 |
| `persistence/` | checkpointer、store、业务仓储接口和实现工厂 | 业务路由、prompt 或模型调用 |
| `models/` | LLM、Embedding、Reranker provider 隔离和构造 | 保存 API key、业务流程决策 |
| `guardrails/` | 输入、输出、检索内容、secret/PII 安全检查 | 业务数据授权的最终判断 |
| `api/` | HTTP 校验、依赖注入、状态码和 DTO 投影 | graph 组装、业务计算、硬编码 tenant |
| `evals/` | 版本化数据集、评估器、阈值和离线 runner | 生产请求路径中的隐式质量判断 |
| `adapters/` | 平台、物流、支付等外部系统协议适配和 mock/real 实现切换 | Agent 路由、审批决策、绕过 ToolExecutor 的直接调用 |
| `domain/` | 稳定业务实体、枚举、值对象和领域错误 | HTTP、LangGraph、provider SDK 实例 |
| `observability/` | trace schema、span/event recorder、脱敏和关联 ID | 业务状态真源、原始 secret 或无保留策略的大 payload |
| `prompts/` | prompt 模板、版本、required/forbidden context | API key、运行时连接、未版本化内联 prompt |
| `schemas/` | API、runtime、tool 和跨模块 DTO | 业务计算和副作用 |
| `rag/` | 摄取、检索、上下文组装、引用和质量评估 | 实时交易事实真源、授权后的补救过滤 |
| `workflows/` | 按业务流程内聚 graph/state/edges/nodes | 跨工作流共享服务的重复实现 |
| `mock_data/` | 版本化演示数据和测试样本 | 生产运行时动态状态 |
| `configuration.py` | 类型化环境配置、profile 选择、启动前校验 | 创建业务仓储、记录 secret 明文 |
| `runtime/` | ApplicationContainer、GraphRuntimeContext、依赖生命周期 | 领域计算、HTTP DTO、把依赖写入 state |

## 6. LangGraph 运行时设计

### 6.1 图导出

`backend/langgraph.json` 导出三张独立图：

- `product_launch`
- `operations`
- `support`

每个 `graph.py` 在模块加载时通过工厂获取 checkpointer 和 store，只编译一次。FastAPI 不在每次请求中重新构建图。

配置形态固定为：

```json
{
  "$schema": "https://langgra.ph/schema.json",
  "dependencies": ["."],
  "graphs": {
    "product_launch": "./src/app/workflows/product_launch/graph.py:graph",
    "operations": "./src/app/workflows/operations/graph.py:graph",
    "support": "./src/app/workflows/support/graph.py:graph"
  },
  "env": ".env"
}
```

### 6.2 依赖所有权与 Runtime Context

应用进程只创建一个 `ApplicationContainer`。它拥有共享 checkpointer、共享 store、repository implementations、ToolExecutor 和 provider clients。三张图从同一个 container 获取依赖，避免每张图得到互不相通的 Store。测试不使用该默认单例，而是显式创建带 fake dependencies 的隔离 container。

请求级可信身份不写入 state，也不和仓储实例混放。LangGraph 使用可序列化、不可变的 `GraphRuntimeContext`：

```python
@dataclass(frozen=True)
class GraphRuntimeContext:
    tenant_id: str
    subject_id: str
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
    trace_id: str
    run_id: str
```

Graph 通过 `StateGraph(State, context_schema=GraphRuntimeContext)` 声明 context。API 在每次 start/resume 时依据认证结果重新构造 context：

```python
result = graph.invoke(
    command,
    config={"configurable": {"thread_id": execution.thread_id}},
    context=runtime_context,
)
```

Repository、ToolExecutor 和 service 通过 graph build-time dependency injection 进入节点闭包，节点禁止在执行时调用全局 getter：

```python
def make_publish_node(tool_executor: ToolExecutor):
    def publish_node(state: ProductLaunchState, runtime: Runtime[GraphRuntimeContext]) -> dict:
        result = tool_executor.execute(
            state=state,
            request_context=runtime.context,
        )
        return {"publish_results": [result]}

    return publish_node
```

`graph.py` 仍只负责把已经构造好的节点装配进图；依赖对象由 `runtime/container.py` 创建。`api/dependencies.py` 与模块级 graph 都通过同一个缓存 container 获取实例。生产环境禁止绕过认证 API 直接暴露 graph invoke；LangGraph CLI 仅用于本地开发并注入明确的 demo context。

### 6.3 Product Launch 单图流程

```text
product_research
  -> profit_analysis
  -> supplier_evaluation
  -> localization
  -> listing_validation
  -> risk_review
  -> ensure_approval
  -> approval_gate / interrupt
  -> route_after_approval
       approved -> verify_approval -> publish_listing -> complete
       rejected -> reject_complete
       expired/revoked -> approval_invalid
```

`ensure_approval` 幂等创建业务审批记录并绑定待发布内容摘要。`approval_gate` 只负责 `interrupt()`。恢复请求先在应用层校验审批事实，再通过 `Command(resume=ApprovalDecision)` 恢复同一个 thread。第二张 publish graph 退役。

中断与恢复契约固定为：

| 契约 | 必需字段 |
|---|---|
| `ApprovalIntent` | schema_version、approval_id、tenant_id、workflow_id、graph_id、tool_name、tool_version、actor_id、listing_version_ids、marketplaces、canonical_input_hash |
| `ApprovalInterrupt` | schema_version、approval_id、intent_digest、reason_codes、risk_level、expires_at |
| `ApprovalDecision` | schema_version、approval_id、status、intent_digest、reviewer_subject、decision_version、decided_at |

`intent_digest` 使用 SHA-256 计算：先将 schema-versioned `ApprovalIntent` 以 UTF-8、`sort_keys=True`、`separators=(",", ":")`、`ensure_ascii=False` 序列化，再计算小写十六进制摘要。任何 listing version、marketplace、tool version、actor 或输入变化都会生成不同摘要。

执行顺序固定为：

1. `ensure_approval` 以 `(tenant_id, approval_id)` 幂等 upsert pending intent；相同 ID 但 digest 不同返回冲突。
2. `approval_gate` 调用 `interrupt(ApprovalInterrupt)`；LangGraph 先持久化 checkpoint 和 interrupt。
3. runner 读取精确 `checkpoint_id`、`interrupt_id`，以 CAS 将二者绑定到仍为 pending 且 digest 相同的 Approval。
4. 如果 checkpoint 已写入但绑定步骤失败，`get_view` 和审批入口先运行幂等 reconciliation，再允许用户决策。
5. 审批 API 使用可信 `RequestContext` 写入 approved、rejected、expired 或 revoked 业务事实；请求体不能提供 reviewer 身份或 intent digest。
6. resume 根据 `(tenant_id, workflow_id, approval_id)` 读取已持久化决策，校验 checkpoint、interrupt、digest、decision_version 和 graph revision，再构造 `Command(resume=decision)`。
7. `approval_gate` 将 resume value 写入 state；`route_after_approval` 只有 approved 可以进入 `verify_approval` 和发布，其余状态进入无副作用终态。

重复行为是确定性的：等待中重复 resume 返回 409；发布进行中重复 resume 返回当前视图；completed、rejected、expired 和 revoked workflow 重复 resume 返回已有终态视图，不再次执行 graph 或外部操作。

状态转换如下：

| 当前状态 | 事件 | 下一状态 | 外部副作用 |
|---|---|---|---|
| created/running | 到达 approval gate | awaiting_approval | 仅创建审批事实 |
| awaiting_approval | approve | approved | 无 |
| awaiting_approval | reject | rejected | 无 |
| awaiting_approval | expire/revoke | approval_invalid | 无 |
| approved | resume 验证成功 | publishing | 受控发布 |
| publishing | 全部成功 | completed | 已写发布账本 |
| publishing | 可重试失败 | publish_retryable | 不自动重试未知副作用 |
| publishing | 终态失败 | failed | 保留部分成功结果 |
| 任意终态 | 重复 resume | 原状态 | 无 |

### 6.4 标识规则

- `graph_id` 是固定枚举：`product_launch`、`operations`、`support`。
- `workflow_id` 是对外业务标识，使用 `wf_` 加 UUIDv4；全局随机，但所有查询仍必须带 tenant scope。
- `thread_id` 是内部 `th_` 加 UUIDv4，不可预测且不对客户端开放。
- `(tenant_id, graph_id, workflow_id)` 唯一映射到一个 `thread_id`，映射与 WorkflowExecution 在同一原子操作中创建。
- `run_id` 是每次 start 或 resume 调用生成的 `run_` 加 UUIDv4；同一 workflow/thread 可以有多个按时间排序的 run。
- start 接受 `Idempotency-Key`。相同 tenant、graph、key 和 request digest 返回已有 execution；相同 key 但 digest 不同返回 409；未提供 key 时创建新 workflow。
- 客户端不能直接提交或覆盖 `thread_id`、`checkpoint_id`、`interrupt_id`。
- 当前基于请求 SHA-1 截断生成 workflow ID 的做法仅视为 legacy 测试输入，迁移后不再用于新 workflow。
- 每个执行记录保存 `graph_revision` 和 `state_schema_version`，恢复时校验兼容性。

MVP 的 `runtime_mode` 固定为 `native_v1`。当前仓储全部为进程内内存实现，不存在可跨部署保留的生产 workflow，因此本次迁移不迁移活跃 legacy checkpoint；部署前清空演示状态。未来出现真实持久化 legacy 数据时必须新增独立迁移 ADR，不在本次实现中伪造 checkpoint。

版本兼容规则：

| 条件 | 恢复行为 |
|---|---|
| graph revision 与 state schema 完全匹配 | 允许恢复 |
| revision 不同但位于该图显式 `SUPPORTED_REVISIONS` 且 schema 相同 | 运行已注册的兼容验证后恢复 |
| state schema 不同且存在纯函数迁移器 | 先生成新 checkpoint 分支并保留原 checkpoint，再恢复 |
| 无兼容声明或迁移器 | 返回 409 `workflow_revision_unsupported`，不执行节点 |

`graph_revision` 是工作流包内显式常量，例如 `product-launch/v2`；`state_schema_version` 是正整数。二者都进入 state、WorkflowExecution、trace 和离线评估产物。

### 6.5 State 规则

State 只保存恢复后继续执行所需的数据或稳定业务对象引用，不复制审批记录、trace 全文或跨 thread 记忆。列表型增量字段使用 `Annotated` reducer；需要整体替换的字段显式返回完整值。

State 中禁止保存：

- API key、数据库连接、HTTP 客户端和模型实例。
- 未裁剪的原始文档全文或大体积 provider 响应。
- 由请求 body 自报且未经认证的权限结论。
- 无 schema 的任意深层 payload。

## 7. 持久化边界

### 7.1 Checkpointer

Checkpointer 保存 thread 范围内的 graph checkpoint。MVP 默认使用 `InMemorySaver`；生产工厂预留 PostgreSQL 实现。生产模式选择 PostgreSQL 后，如果连接配置缺失，应用必须拒绝启动。

内存 MVP 的能力边界明确为单进程、单 worker：它可以验证同一进程内的 interrupt/resume、graph 重新构建后复用同一 saver，以及幂等和租户逻辑，但不宣称跨进程、进程重启或多 worker durable。跨进程恢复、lease/fencing 和崩溃注入测试属于 PostgreSQL integration profile，启用生产持久化后才作为发布门禁。

`ApplicationContainer` 在进程内只创建一个 saver、一个 store 和一组业务仓储，三张 graph 共享这些实例。测试通过新建 container 实现隔离和重置，禁止修改模块级单例内部状态来实现测试清理。

### 7.2 Store

Store 只用于跨 thread 的长期数据：

- 租户偏好：namespace 为 `("tenant", tenant_id, "commerce_memory")`，key 为 policy 名称。
- 全局 playbook：namespace 为 `("global", "playbooks")`，key 为 playbook 名称。

Approval、Trace、发布账本和交易事实不写入 Store。
全局 namespace 只允许受信系统管理员写入，普通租户不能枚举或覆盖；读取后仍按 agent profile 过滤允许使用的 playbook。

### 7.3 业务仓储

- `WorkflowExecutionRepository`：保存 workflow/thread 绑定和运行模式。
- `ApprovalRepository`：保存审批请求、内容摘要、审批主体、决策版本和 checkpoint 绑定。
- `TraceEventRepository`：保存可审计业务事件和运行关联字段。
- `PublishOperationRepository`：保存外部发布请求哈希、状态、provider 结果、attempt 和 fencing token。
- `SemanticCheckpointRepository`：仅为兼容 API 投影命名 snapshot，不伪造 LangGraph checkpoint。

所有仓储以 `(tenant_id, resource_id)` 作为归属边界，不允许只凭资源 ID 越过租户校验。

## 8. API 与依赖注入

`api/dependencies.py` 提供：

- 认证后的 `RequestContext`。
- Product Launch、Operations 和 Support graph。
- 运行时 service、ToolExecutor 和 repository interfaces。

`RequestContext` 至少包含 `tenant_id`、`subject_id`、roles、permissions、trace_id。租户和审批者身份不再由业务请求体自报。

应用层暴露稳定边界：

- `start(command, request_context)`
- `resume(workflow_id, approval_id, request_context)`
- `get_view(workflow_id, request_context)`

现有 HTTP 路径和核心返回字段在迁移阶段保持兼容。内部原生 checkpoint 通过兼容 DTO 投影为已有 snapshot 视图，不直接暴露 LangGraph 内部表结构。

`resume` 不接受客户端提交的 decision；它只读取已经由审批 API 持久化的 `ApprovalDecision`。兼容范围固定为当前 `POST /workflows`、`POST /workflows/{workflow_id}/resume`、`GET /workflows/{workflow_id}/events` 以及审批路由的路径、成功字段和既有 404/409 语义。新增内部字段只通过新的 typed response model 输出，不返回原生 checkpoint payload。

兼容字段清单：

- create response 保留 `workflow_id`、`state`、`product_idea`、`target_marketplaces`、`target_locale`、`profit_estimate`、`supplier_evaluations`、`selected_supplier_id`、`supplier_risk_level`、`listing_drafts`、`localized_listings`、`listing_versions`、`selected_listing_version_ids`、`approved_listing_version_ids`、`localization_risk_flags`、`listing_validations`、`approval_required`、`approval_request_id`、`approval_request`、`approval_reasons`、`snapshot`、`completed_steps`。
- resume response 保留 `workflow_id`、`state`、`approval_request_id`、`publish_results`、`target_locale`、`listing_drafts`、`localized_listings`、`listing_versions`、`selected_listing_version_ids`、`approved_listing_version_ids`、`localization_risk_flags`、`tool_calls`、`completed_steps`。
- events response 保留 `workflow_id` 和 `events`。
- approval response 保留 `id`、`workflow_id`、`tenant_id`、`requested_by`、`reason_codes`、`risk_level`、`resource_type`、`resource_id`、`status`、`metadata`、`created_at`、`reviewed_at`、`reviewed_by`、`review_comment`，并允许新增 checkpoint/digest/version 字段。

唯一有意的安全破坏性变更是 approval action request 删除 `reviewer_id`；reviewer 必须来自认证上下文。开发 profile 可以使用仅本地启用的 demo auth headers，生产 profile 禁止 demo identity provider。

## 9. ToolExecutor 与外部副作用

本次迁移完成后，所有真实或模拟外部操作都必须通过 ToolExecutor。纯内存、无副作用的确定性业务计算可以继续由 service 直接提供。ToolExecutor 执行顺序固定为：

1. 解析工具定义和版本。
2. 校验 agent profile 和工具白名单。
3. 校验 tenant、permission 和审批证明。
4. 校验输入 schema 和不可变执行摘要。
5. 查询幂等记录。
6. 按策略执行 timeout 和 retry。
7. 校验输出 schema。
8. 在同一 repository transaction 中持久化执行结果和 outbox event。
9. 返回标准化 ToolResult。

高风险发布操作的审批证明必须绑定：tool name、tool version、完整输入 hash、actor、tenant、workflow 和 listing version。Checkpointer 的 pending writes 不等于外部 exactly-once，真实连接器必须继续依赖 PublishOperation ledger、provider idempotency key 或 outbox。

PublishOperation 状态机固定为：

| 状态 | 含义 | 允许转换 |
|---|---|---|
| pending | 已登记，尚未取得执行权 | executing |
| executing | 持有 lease/fencing token 的 worker 正在调用 provider | succeeded、failed_retryable、failed_terminal、unknown |
| succeeded | provider 结果和 outbox 已原子提交 | 无 |
| failed_retryable | 已确认 provider 未产生副作用，可以重试 | executing |
| failed_terminal | 业务或 provider 明确拒绝，不再重试 | 无 |
| unknown | provider 可能成功但本地没有可信结果 | reconciling |
| reconciling | 按 provider idempotency key 查询真实结果 | succeeded、failed_retryable、failed_terminal、unknown |

执行权通过 CAS 将 pending/failed_retryable 转为 executing 并签发 fencing token。provider 超时、连接中断或成功响应丢失一律进入 unknown，禁止盲目重试；reconciler 优先用 provider idempotency key 查询，provider 不支持查询时升级人工。业务数据库实现必须在同一事务中提交 operation outcome 与 outbox；MVP 内存实现只在单进程锁内模拟原子性，不宣称进程崩溃安全。

## 10. 模型与硅基流动配置

`models/providers/siliconflow.py` 封装 OpenAI-compatible HTTP 客户端构造；`llm.py`、`embeddings.py`、`reranker.py` 只暴露稳定 provider-neutral 接口。

MVP 默认模型与现有配置保持一致：

- LLM：`deepseek-ai/DeepSeek-V3.2`
- Embedding：`BAAI/bge-m3`
- Reranker：`BAAI/bge-reranker-v2-m3`
- Vision：`Qwen/Qwen3-VL-32B-Instruct`

实现优先使用 `langchain-openai` 的 OpenAI-compatible 客户端并注入 SiliconFlow `base_url`；业务图不直接依赖具体 SDK 类型。

配置来源为环境变量和 `configuration.py`：

- `SILICONFLOW_API_KEY`
- `SILICONFLOW_BASE_URL`
- `LLM_MODEL`
- `EMBEDDING_MODEL`
- `RERANKER_MODEL`
- `VISION_MODEL`

API key 不写入代码、fixture、state、checkpoint、trace、日志或文档。默认单元测试使用 fake provider，不调用真实模型。

`configuration.py` 使用 `SecretStr` 保存 key，日志 formatter 对 secret-like key/value 二次脱敏；`.env.example` 只保留空值，`backend/.gitignore` 和仓库根 `.gitignore` 都忽略 `.env`。`MODEL_ENABLED=false` 时确定性 MVP 可以在无 key 条件下启动；`MODEL_ENABLED=true` 或生产 profile 声明某模型为必需能力时，缺少 key 必须 fail fast。CI 运行 tracked-file secret scan，禁止提交符合 `sk-` 等模式的凭据。

## 11. 客服 Routed RAG

客服图使用可测量的 Routed RAG baseline，不在没有评估证据时加入循环式 Agentic RAG。

```text
normalize/authenticate
  -> planner
  -> policy route
     -> ACL lexical retrieval
     -> transaction tool request
     -> off-topic/refusal
  -> context assembly
  -> evidence sufficiency
  -> grounded response or human escalation
```

约束：

- 静态政策、FAQ、平台规则进入知识索引。
- MVP 检索策略固定为 ACL 预过滤词法检索；向量、hybrid 和 reranker 只在离线指标证明有收益后新增。
- 订单状态、物流轨迹、支付、退款和优惠券等实时事实走 ToolExecutor，不向量化为事实真源。
- tenant 和 ACL 过滤在候选文本进入模型上下文前完成。
- 检索文档被视为不可信输入，不能选择工具、权限或收件人。
- 每个知识回答包含真实 source locator；无证据、证据过期或权限不足时 fail closed 并升级人工。
- 流式和非流式响应共用同一 graph，只在事件输出层存在差异。

核心 typed contracts 至少包含：

| 契约 | 必需字段 |
|---|---|
| `SupportRequest` | trace_id、tenant_id、ticket_id、query、permission_scopes、marketplace、locale、effective_at、entity_refs |
| `EntityReferences` | order_id、shipment_id、payment_id、refund_id、sku、coupon_code、customer_id 中已知的值 |
| `PlannerDecision` | intent、routes、filters、tool_requests、reason_code、clarification_fields |
| `RetrievalFilters` | tenant_id、permission_scopes、marketplace、locale、product_id、effective_at |
| `SupportSource` | source_id、tenant_id、authority、permission_scopes、policy_version、effective range、index_version、locator |
| `RetrievalCandidate` | chunk_id、source_id、text、score、locator、permission_decision_id |
| `SupportCitation` | source_id、title、locator、supports |
| `SupportResponse` | status、answer、citations、tool_results、reason_code、human_escalation、final trace_id |

Planner 路由矩阵固定为：

| 输入类型 | routes | 行为 |
|---|---|---|
| 静态政策/FAQ | knowledge | ACL 词法检索、上下文组装、引用回答 |
| 实时交易事实且实体 ID 完整 | transaction | ToolExecutor 查询 |
| 同时包含政策与交易问题 | knowledge + transaction | 先分别取证，再统一组装；任一分支无证据时明确标记 |
| 交易问题缺少必需实体 ID | clarification | 返回需要补充的字段，不猜测 ID |
| 法律威胁或高风险投诉 | escalation | 转人工，不自动生成承诺 |
| 离题 | refusal | 安全拒绝或引导回客服范围 |
| 无证据、过期或 ACL denied | escalation | fail closed，不泄露受限来源是否存在 |

交易工具名称和最小实体契约固定为：

| 工具 | 必需实体引用 |
|---|---|
| `get_order_status` | `order_id` |
| `get_shipment_trajectory` | `shipment_id` 或 `order_id`，至少一个 |
| `get_payment_status` | `payment_id` 或 `order_id`，至少一个 |
| `get_refund_amount` | `refund_id` 或 `order_id`，至少一个 |
| `get_inventory_status` | `sku` |
| `get_coupon_status` | `coupon_code` |
| `get_ticket_history` | `customer_id` |

以上七个工具必须同时存在于 ToolRegistry、Customer Support profile 白名单、typed handler catalog 和 contract tests。Planner 不得把 query 文本中未经校验的任意字符串当作实体 ID。

## 12. 错误、重试与并发

- 模块边界使用类型化错误，API 统一映射 400、401、403、404、409、422、429 和 5xx。
- State 只保存可恢复的错误码、阶段和摘要，不保存异常对象或敏感堆栈。
- 确定性只读工具可以按声明策略重试；高风险副作用没有幂等证明时禁止自动重试。
- 同一 thread 的并发 resume 使用 lease 或乐观版本控制；旧 worker 通过 fencing token 失效。
- approve/reject 竞争、重复 resume 和完成后 resume 必须返回确定性结果。
- trace 写入失败不能让已成功副作用被再次执行，trace 通过去重键和 outbox 补写。
- 图版本或 state schema 不兼容时停止恢复并返回可诊断错误，不盲目解释旧 checkpoint。

## 13. 安全与 Guardrails

- API 认证上下文是 tenant、subject 和权限的唯一真源。
- checkpoint、store、repository、RAG index 和 cache 都执行租户隔离。
- 状态保存前递归检查字典、列表和嵌套对象中的 secret-like key/value。
- trace 使用摘要、资源 ID 和哈希，不默认保存完整 prompt、检索文本或 PII。
- 输入 guard 校验长度、结构、危险指令和业务约束。
- retrieved content guard 标记 prompt injection、过期和低可信来源。
- 输出 guard 校验引用、敏感数据、禁限售声明和无证据断言。
- time-travel、replay 或 checkpoint 恢复不得绕过审批和 PublishOperation ledger。

## 14. 可观测性

TraceEvent v2 至少包含：

- `event_id`、`trace_id`、`run_id`、`thread_id`、`workflow_id`、`tenant_id`。
- `checkpoint_id`、`task_id`、`node_name`、`attempt`、`sequence`。
- `tool_name`、`tool_version`、`prompt_version`、`model_version`。
- latency、status、error_code、retry_reason 和 privacy-safe metadata。

业务事件与 LangGraph runtime span 相互关联但不互相替代。崩溃前已完成的节点、工具和审批动作必须有可重放的审计记录。

## 15. 测试与评估

### 15.1 测试层次

- `unit/`：service、edge、guardrail、reducer、ToolExecutor 策略和 DTO。
- `contract/`：state、tool、trace、planner、retrieval candidate、citation、stream event。
- `integration/`：完整 graph、checkpointer/store、repository、RAG index 和 API dependencies。
- `e2e/`：固定本地数据上的创建、审批、恢复、发布、运营诊断和客服回答。
- `evals/`：版本化离线场景、指标、阈值、产物和回归比较。

默认测试必须 mock LLM、Embedding、Reranker、真实数据库和外部平台。需要真实服务的测试必须显式标记，不进入快速默认测试。

### 15.2 必测场景

- graph 在每个关键节点前后中断并恢复。
- interrupt 写入、审批写入和 Command resume 的故障窗口。
- 重复创建、重复审批、重复 resume 和完成后 resume。
- 多 worker 并发 resume 和 fencing。
- 多平台部分发布成功后的恢复与幂等。
- 跨租户 workflow、approval、checkpoint、store、event 和 RAG 检索访问。
- 旧审批复用于新 listing hash、工具版本或 actor 的攻击。
- 深层列表中的 secret、恶意检索文档和伪造引用。
- 客服 no-answer、off-topic、ACL denied、stale evidence 和 human escalation。
- 流式最终结果与非流式响应一致。

### 15.3 合并与发布门禁

迁移完成后的标准工作目录为 `backend/`，CI 依次执行：

```text
python -m compileall -q src/app
python -m pytest -q
python -m pytest tests/contract/test_langgraph_manifest.py -q
python evals/run_evals.py --suite product_launch --output outputs/evals/product-launch-v1.json
python evals/run_evals.py --suite operations --output outputs/evals/operations-v1.json
python evals/run_evals.py --suite support --output outputs/evals/support-v1.json
python evals/run_evals.py --suite all --gate --output outputs/evals/all-v1.json
```

仓库根目录执行：

```text
git diff --check
python backend/scripts/scan_secrets.py --tracked --staged --history-base origin/main --env-example backend/.env.example
```

Secret scanner 必须检查全部 tracked 文件，包括 `*.example`；检查 staged diff；检查 `merge-base(origin/main, HEAD)..HEAD` 的新增和删除 diff。`.env.example` 中所有包含 `KEY`、`TOKEN`、`SECRET`、`PASSWORD` 的变量必须为空值或显式 `${ENV_VAR}` 引用，不能用形似真实凭据的示例值。scanner 产出 privacy-safe JSON 报告并以非零状态阻断提交/CI，不在报告中回显命中的完整 secret。

Product Launch v1 数据集必须恰好包含七个 scenario：`adapter-validation-failure`、`high-risk-supplier`、`localization-claim`、`low-profit`、`missing-approval`、`tampered-version-hash`、`three-platform-approved-publish`。每个结果必须恰好包含以下八个 metric：

- `identity_match`
- `state_and_risk_match`
- `approval_and_snapshot_match`
- `listing_version_match`
- `validation_match`
- `publish_match`
- `trace_match`
- `error_match`

每个 metric 和总分的 threshold、score 必须为 `1.0`，status 必须为 passed。Expectation 保存的 hash 必须等于规范化 expected summary 的 SHA-256；result 保存的 actual hash 必须等于规范化 actual summary 的 SHA-256；精确 golden case 要求两者相等。metrics 为空、名称重复、集合不完整、scenario 缺失或多余都 fail closed。

评估哈希统一使用 `canonical-json/v1`：先按对应 Pydantic schema 严格验证，再以 `model_dump(mode="json", exclude_none=False)` 获取基础对象；enum 使用 value；datetime 转为 UTC RFC3339 `YYYY-MM-DDTHH:MM:SS.ffffffZ`；Decimal 转为无指数十进制字符串并去除无意义尾零；object key 按 Unicode code point 升序；JSON 使用 UTF-8、`ensure_ascii=False`、`sort_keys=True`、`separators=(",", ":")`。数组默认保留契约顺序；语义无序字段在序列化前按稳定键排序：reason/error/source ID 字符串按字典序，listing validation/version/publish 按 `(marketplace, listing_version_id 或 version_id)`，metric 按 name。最终计算小写 SHA-256 十六进制摘要。

Support v1 必须恰好包含十类且每类至少一例：`product_fact`、`current_return_policy`、`marketplace_isolation`、`transaction_route`、`no_answer`、`off_topic`、`same_tenant_acl_denial`、`cross_tenant_denial`、`stale_policy`、`prompt_injection`。门禁为：

- permission leak rate = 0
- citation precision >= 0.95
- no-answer accuracy >= 0.90
- prompt-injection success rate = 0
- failed case IDs 为空
- 所有指标分母大于 0；空分类不能按 0 比率通过
- deterministic baseline 的 model call count = 0、provider cost = 0、CI p95 latency <= 2 秒

Operations v1 必须恰好包含七类：`healthy_control`、`low_stock`、`shipment_delay`、`conversion_drop`、`return_rate_rise`、`all_stale`、`tenant_or_version_conflict`。每类预期 status、anomaly type、evidence IDs 和 proposal IDs 精确匹配；proposal 的 `execution_allowed` 必须全部为 false；跨租户泄漏为 0；空分类 fail closed。

Tool contract gate 必须证明：七个客服交易工具和所有 Product Launch 工具均存在 registry、profile、schema 和 handler；高风险工具无审批不能执行；相同幂等键和输入只能产生一次 handler 副作用；相同键不同输入返回冲突；trace 失败不会重放已成功副作用。

所有 eval 产物使用统一 JSON envelope，包含 `schema_version`、canonicalization_version、suite、dataset_version、graph_revision、state_schema_version、model_versions、index_version、started_at、duration_ms、case_count、metrics、failed_case_ids 和 artifact_hash。`artifact_hash` 使用同一 `canonical-json/v1` 对完整 envelope 计算，但必须先移除 `artifact_hash` 字段；`started_at` 和 `duration_ms` 参与摘要，因此 artifact hash 用于校验单个产物完整性，不用于比较不同运行。CI 将 `outputs/evals/*.json` 上传为构建产物，不提交运行产物到 Git。

此外必须满足：`langgraph.json` 中三个导出目标均可动态 import；引用字段来自真实 source metadata，不生成占位定位；任何未解决 Critical 或 Important 评审项阻止合并。

## 16. Node 16-19 合并前门禁

共同 merge base 为 `106544d7d7dd8585da387c946375ef2f0ad44200`。四个分支没有文件级冲突，使用 `git merge --no-ff` 按 Node 16、17、18、19 顺序进入 `codex/langgraph-standard-runtime-integration` 独立 worktree。

| 顺序 | 分支与审计 HEAD | 问题 ID | 合并前精确条件 | 负责人 |
|---|---|---|---|---|
| 1 | `codex/node-16-product-launch-golden-evals` / `6cac2a0a3b1b20a87c8ba99c3bbba3143129cd08` | LG16-EVAL-01 | 七个 scenario、八项固定 metric、非空集合、唯一名称、threshold/score、expected/actual canonical hash 全部 fail closed | 集成负责人 |
| 2 | `codex/node-17-tool-executor` / `baf88ed4d95aa08cc3ae23e32fac57eb0c25955f` | LG17-EXEC-01 | 审批证明绑定 tenant、workflow、actor、tool/version、完整输入 hash；幂等结果与 outbox 先于可失败 trace 提交 | 集成负责人 |
| 3 | `codex/node-18-operations-agent` / `cf558d222c4ad8b12f4a98eb79e83bba42555027` | LG18-OPS-01 | 每个 order_id 按 occurred_at、received_at、event_id 依次选最新事件；仅最新状态 paid/fulfilled 计入 gross revenue，pending/cancelled/returned/refunded 排除；汇总按 currency 分区且禁止跨币种求和；空白 identity 拒绝；`git diff --check` 通过 | 集成负责人 |
| 4 | `codex/node-19-support-rag` / `7d3ae55922d0ecf63428f3b9124c25424a37428f` | LG19-RAG-01 | 七个交易工具与 registry/profile/schema/handler 一致；必需实体 ID 交叉校验；十类评估非空且门禁 fail closed | 集成负责人 |

每个分支先在自己的 worktree 修复并追加中文提交，再由集成 worktree 合并。每次合并后在 `backend/` 依次执行对应聚焦测试和全量测试：

```text
python -m pytest tests/test_product_launch_golden.py -q
python -m pytest -q

python -m pytest tests/test_tool_executor.py -q
python -m pytest -q

python -m pytest tests/test_operations_agent.py -q
python -m pytest -q

python -m pytest tests/test_support_rag.py -q
python -m pytest -q
```

每次合并同时执行仓库根目录的 `git diff --check`。聚焦或全量验证失败时立即停止后续合并，修复回原节点分支并重新评审，不在集成分支叠加不相关补丁。

以上问题关闭后，先运行合并后全量测试，再开始目录移动，避免四个分支各自重写 import 和 fixture 路径。

## 17. 迁移顺序

1. 创建独立集成分支和 worktree，保持主工作区已有的 `docs/progress/2026-07-10-node-09-approval-request-api.md`、`docs/superpowers/plans/2026-07-10-approval-request-api.md`、`docs/superpowers/plans/2026-07-10-approved-publish-resume.md` 不变。
2. 逐分支评审、修复、合并 Node 16-19，并运行全量回归。
3. 增加 `pyproject.toml`、`langgraph.json`、项目配置和 graph 导入 smoke test。
4. 增加 `api/app.py`、后端 README、Dockerfile、脚本、迁移目录和 CI 基线，统一由 `pyproject.toml` 管理依赖。
5. 迁移源码到 `backend/src/app/`，同步更新 import、fixture 路径和测试分层。
6. 将每张业务图重构为标准 `graph/state/edges/nodes` 结构。
7. 增加 API dependencies、RequestContext、WorkflowExecution 和 repository interfaces。
8. 接入 InMemorySaver/InMemoryStore、稳定 thread_id 和单图 interrupt/resume。
9. 收敛 ToolExecutor、发布账本、trace/outbox 和安全 guardrails。
10. 接入 SiliconFlow provider-neutral models 层，默认测试继续使用 fake provider。
11. 完成全量测试、离线评估、graph 加载和 reader review 后合并回主分支。

## 18. MVP 扩展点

- Checkpointer/Store 工厂可替换为 PostgreSQL 实现。
- Repository protocols 可替换为 SQLAlchemy 或其他持久化实现。
- Tool catalog 可增加真实 marketplace、ERP、物流和支付连接器。
- `langgraph.json` 可继续注册选品、广告、采购、定价、财务和合规工作流。
- Support RAG 可在 baseline 指标证明需要时增加向量检索、reranker 和有界 evaluator/refiner。
- Model provider 可以在不修改业务图的情况下增加备用供应商、熔断和成本路由。
- Trace contract 可映射 OpenTelemetry 或 LangSmith，而不改变业务审计事件结构。

## 19. 验收标准

1. 最终源码只从 `backend/src/app/` 导入，不保留旧 `backend/app/` 实现。
2. FastAPI 从 `app.api.app:app` 启动；三张业务图均能由 `langgraph.json` 加载，并通过 API dependencies 复用模块级实例。
3. Product Launch 使用同一 `thread_id` 完成 interrupt 和 resume，不再启动第二张发布图。
4. Approval、Trace、Store、Checkpointer 和 PublishOperation 的职责可由代码和测试分别证明。
5. API key 不出现在 Git 历史新增内容、state、checkpoint、trace、fixture 或测试输出中。
6. Node 16-19 的重要评审问题全部关闭，合并后全量测试和迁移后全量测试均通过。
7. unit、contract、integration、e2e 和 evals 的目录及执行入口清晰可用。
8. 新增工作流时可以复制标准 workflow package 骨架，而无需修改现有业务图内部实现。
9. `pyproject.toml` 是唯一依赖真源，后端 README、Dockerfile、CI 和实际命令保持一致。
