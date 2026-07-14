# Support、模型、Guardrails 与质量门禁实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将客服 baseline 扩展为标准多节点 Routed RAG graph，加固七个交易工具的可验证证据契约，并补齐 SiliconFlow provider-neutral 模型层、三层 Guardrails、三套离线评估、Agent Harness、secret scanner 和 CI 发布门禁。

**Architecture:** Support graph 以 deterministic planner 路由 ACL 词法知识检索和 ToolExecutor 交易查询；mixed 请求分别取证后汇总，无证据 fail closed。模型层通过 ports 隔离 SiliconFlow，默认 baseline 和 CI 使用 fake/disabled provider。统一 canonical-json/v1 为评估产物封印，CI 顺序执行结构、测试、安全和质量门禁。

**Tech Stack:** Python 3.12, LangGraph 1.2.9, Pydantic 2.11.7, langchain-openai 1.x, httpx 0.28.1, pytest 8.4.1, GitHub Actions.

## Global Constraints

- 前置分支必须完成 src layout 和原生 Product Launch runtime；manifest 已导出三张图。
- Support deterministic baseline 的 `model_call_count=0`、`provider_cost=0`；禁止在测试或评估中调用真实网络。
- 不读取本地 `.env` 或真实 key；所有 provider 测试使用 stub constructor/transport 和合成 secret。
- tenant/ACL 过滤必须在候选文本评分和进入上下文前完成；post-generation 过滤不能作为授权。
- Planner 禁止从自然语言 query 猜实体 ID；交易参数只来自已验证 `EntityReferences`。
- 流式与非流式使用同一 graph；只允许事件输出层不同。
- 开始本计划前，从 progress log 唯一提取 `HITL_FINAL_SHA`，校验格式、Git 对象和祖先关系；使用下方命令，任一步非零立即停止。
- 所有阶段提交最终合入并推送 `dev-com`；节点 Agent 可以使用独立功能分支，但本阶段禁止合并或推送 `main`。
- 每个任务 RED/GREEN、聚焦/全量测试、`git diff --check`、中文提交；复杂安全和 RAG 代码添加必要中文注释。

```powershell
$progressPath = "docs/progress/2026-07-14-langgraph-standard-runtime-integration.md"
$shaLines = @(Get-Content -Encoding UTF8 $progressPath | Where-Object {
    $_ -match '^HITL_FINAL_SHA=[0-9a-f]{40}$'
})
if ($shaLines.Count -ne 1) { throw "HITL_FINAL_SHA must appear exactly once" }
$hitlFinalSha = $shaLines[0].Split('=', 2)[1]
git cat-file -e ($hitlFinalSha + "^{commit}")
if ($LASTEXITCODE -ne 0) { throw "HITL_FINAL_SHA is not a commit" }
git merge-base --is-ancestor $hitlFinalSha HEAD
if ($LASTEXITCODE -ne 0) { throw "HITL_FINAL_SHA is not an ancestor" }
```

---

### Task 1: 七个交易工具的交易证据契约加固

**Files:**
- Modify: `backend/src/app/domain/support.py`
- Modify: `backend/src/app/tools/catalog/support.py`
- Modify: `backend/src/app/adapters/support_transactions.py`
- Modify: `backend/src/app/mock_data/support_transactions/v1.json`
- Create: `backend/tests/contract/test_support_tools.py`
- Create: `backend/tests/integration/tools/test_support_tools.py`

**Interfaces:**
- Consumes: Node 19 已交付的 `EntityReferences`、七个严格 Input/Output model、handlers 与 ToolExecutor
- Produces: `TransactionEvidence` and evidence-bearing output contracts
- Produces: evidence IDs for Support state as a stable deduplicated tuple

- [ ] **Step 1: 写入交易证据字段 RED 测试**

```python
@pytest.mark.parametrize("tool_name", SUPPORT_TRANSACTION_TOOL_NAMES)
def test_each_transaction_output_exposes_verifiable_evidence(tool_name):
    definitions = {item.name: item for item in build_support_tool_definitions()}
    assert {
        "evidence_id",
        "source_system",
        "entity_id",
        "observed_at",
    } <= definitions[tool_name].output_model.model_fields.keys()
```

另测 `evidence_id` 必须为 `sha256:<64 lowercase hex>`、`source_system` 非空、`entity_id` 与查询实体相同、`observed_at` 必须含时区；所有输出 model 保持 `extra="forbid"` 和 frozen。

- [ ] **Step 2: 写入 registry/profile/catalog 一致性 RED 测试**

```python
async def test_transaction_handler_returns_stable_tenant_scoped_evidence(container):
    request = support_tool_request(
        "get_order_status", {"order_id": "order-1"}, tenant_id="tenant-a"
    )
    first = await container.tool_executor.execute(request)
    second = await container.tool_executor.execute(request)
    assert first.output["evidence_id"] == second.output["evidence_id"]
    assert first.output["entity_id"] == "order-1"
    assert first.output["source_system"] == "mock_support_transactions/v1"
```

参数化七个工具，并增加跨 tenant 同实体返回不同证据或 not-found、fixture 缺 `observed_at` 时 fail closed、响应不回显 tenant 内部索引的断言。

- [ ] **Step 3: 运行 RED**

Run: `python -m pytest tests/contract/test_support_tools.py tests/integration/tools/test_support_tools.py -q`

Expected: FAIL，现有七工具输出尚未携带统一、可验证的交易证据字段。

- [ ] **Step 4: 实现统一交易证据模型**

```python
class TransactionEvidence(SupportContract):
    evidence_id: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_system: str = Field(min_length=1, max_length=128)
    entity_id: NonEmptyId
    observed_at: datetime

    @field_validator("observed_at")
    @classmethod
    def require_aware_observed_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must be timezone-aware")
        return value
```

七个现有输出 model 继承或组合该契约；`evidence_id` 对 canonical `{tenant_id, tool_name, entity_id, source_system, observed_at, payload}` 计算稳定 SHA-256，tenant 只参与摘要，不进入公开输出。禁止在本任务重新定义 `EntityReferences`、工具矩阵、registry 或 profile。

- [ ] **Step 5: 实现 tenant-safe 内存 adapter 与 async handlers**

Handler 继续只从 `ToolExecutionContext.tenant_id` 读取租户；adapter 从版本化 fixture 读取 `observed_at`，通过严格输出模型生成证据。Support graph 后续只把验证通过的 `evidence_id` 放入 `transaction_evidence_ids`。

- [ ] **Step 6: 运行 GREEN、全量并提交**

Run: `python -m pytest tests/contract/test_support_tools.py tests/integration/tools/test_support_tools.py -q`

Run: `python -m pytest -q`

```text
git diff --check
git commit -m "功能：加固客服交易工具证据契约"
```

---

### Task 2: Mixed、Clarification 与 Escalation Planner

**Files:**
- Modify: `backend/src/app/rag/support/planner.py`
- Modify: `backend/src/app/rag/support/ports.py`
- Modify: `backend/src/app/domain/support.py`
- Create: `backend/tests/unit/rag/support/test_planner.py`

**Interfaces:**
- Produces: `PlannerDecision(intent, routes, filters, tool_requests, reason_code, clarification_fields)`

- [ ] **Step 1: 写入路由矩阵 RED 测试**

```python
def test_mixed_policy_and_transaction_request_uses_two_routes():
    request = support_request(
        query="What is the refund policy and how much was refunded?",
        entity_refs=EntityReferences(refund_id="refund-1"),
    )
    decision = RuleBasedSupportPlanner().plan(request)
    assert decision.routes == ("knowledge", "transaction")
    assert [item.tool_name for item in decision.tool_requests] == ["get_refund_amount"]


def test_query_text_never_becomes_entity_id():
    request = support_request(query="where is order A-100", entity_refs=EntityReferences())
    decision = RuleBasedSupportPlanner().plan(request)
    assert decision.routes == ("clarification",)
    assert decision.clarification_fields == ("order_id",)
```

覆盖 knowledge、transaction、mixed、多个缺失字段、legal escalation、off-topic refusal、refund policy 优先级和工具请求去重顺序。

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/unit/rag/support/test_planner.py -q`

Expected: FAIL，旧 Planner 只有单 route 且无实体交叉约束。

- [ ] **Step 3: 实现 deterministic 优先级**

优先级固定为 escalation、refusal、entity clarification、mixed、transaction、knowledge。`routes` 使用固定 Literal tuple；tool requests 按七工具常量顺序排序和去重。

- [ ] **Step 4: 运行 GREEN 并提交**

Run: `python -m pytest tests/unit/rag/support/test_planner.py -q`

```text
git diff --check
git commit -m "功能：增加客服混合与澄清路由"
```

---

### Task 3: ACL 预过滤词法检索与引用契约

**Files:**
- Modify: `backend/src/app/rag/support/lexical.py`
- Modify: `backend/src/app/rag/support/context.py`
- Modify: `backend/src/app/domain/support.py`
- Create: `backend/tests/unit/rag/support/test_lexical.py`
- Create: `backend/tests/contract/test_support_retrieval.py`

**Interfaces:**
- Preserves: `SupportRetriever.retrieve(request) -> RetrievalResult`
- Adds: `permission_decision_id` and real locator preservation

- [ ] **Step 1: 写入 ACL prefilter RED 测试**

```python
def test_unauthorized_text_is_never_scored(index, scoring_spy):
    index.ingest(restricted_source(), restricted_chunks())
    result = index.retrieve(request_without_scope())
    assert result.candidates == ()
    assert scoring_spy.texts == []
```

覆盖 tenant、scope subset、公开空 scope、marketplace、locale、product、effective range、tombstone、版本替换、真实 locator 和 `permission_decision_id`。

- [ ] **Step 2: 写入 context budget RED 测试**

断言最多 5 chunks、4000 字符、按 source/chunk 去重、引用号连续、locator 不被重建或猜测。

- [ ] **Step 3: 运行 RED**

Run: `python -m pytest tests/unit/rag/support/test_lexical.py tests/contract/test_support_retrieval.py -q`

Expected: FAIL，部分契约字段或 pre-score spy 保障不存在。

- [ ] **Step 4: 实现 prefilter 和 context assembly**

所有 tenant/ACL/freshness metadata 判断先于访问 candidate text 和计算 score。Context assembler 仅接收已授权 candidates，保留 source locator，并产生 allowed source ID 集合供 output guard 使用。

- [ ] **Step 5: 运行 GREEN、全量并提交**

Run: `python -m pytest tests/unit/rag/support/test_lexical.py tests/contract/test_support_retrieval.py -q`

Run: `python -m pytest -q`

```text
git diff --check
git commit -m "功能：强化客服 ACL 预过滤检索与引用"
```

---

### Task 4: 三层 Guardrails

**Files:**
- Create: `backend/src/app/guardrails/contracts.py`
- Create: `backend/src/app/guardrails/secrets.py`
- Modify: `backend/src/app/guardrails/input_guard.py`
- Modify: `backend/src/app/guardrails/retrieved_content_guard.py`
- Create: `backend/src/app/guardrails/output_guard.py`
- Create: `backend/tests/unit/guardrails/test_input_guard.py`
- Create: `backend/tests/unit/guardrails/test_retrieved_content_guard.py`
- Create: `backend/tests/unit/guardrails/test_output_guard.py`

**Interfaces:**
- Produces: `GuardDecision`, `GuardIssue`, `GuardedCandidate`
- Produces: input/retrieved/output inspection functions

- [ ] **Step 1: 写入深层 secret 和输入 RED 测试**

构造 dict/list/Pydantic 嵌套的合成 secret-like 值，断言 issue 只包含 path/rule/hash prefix，不回显 value。覆盖长度、空白身份、危险 business claims。

- [ ] **Step 2: 写入检索注入和输出引用 RED 测试**

```python
def test_output_guard_rejects_fabricated_citation(response):
    decision = inspect_output(
        response,
        allowed_source_ids=frozenset({"source-1"}),
        transaction_evidence_ids=frozenset(),
    )
    assert decision.allowed is False
    assert "citation_not_allowed" in decision.reason_codes
```

覆盖 prompt injection、过期/unverified 来源、支付敏感信息、无证据断言、退款承诺和 transaction evidence mismatch。

- [ ] **Step 3: 运行 RED**

Run: `python -m pytest tests/unit/guardrails -q`

Expected: FAIL，guard modules 不完整。

- [ ] **Step 4: 实现职责分离**

Retrieved guard 只处理注入、freshness、authority，不承担 ACL；output guard 只接受 allowed source/evidence IDs。阻断时返回无引用、无业务承诺的人工升级响应。

- [ ] **Step 5: 运行 GREEN 并提交**

Run: `python -m pytest tests/unit/guardrails -q`

```text
git diff --check
git commit -m "功能：增加输入检索与输出三层安全护栏"
```

---

### Task 5: 标准多节点 Support Graph

**Files:**
- Modify: `backend/src/app/workflows/support/state.py`
- Modify: `backend/src/app/workflows/support/edges.py`
- Modify: `backend/src/app/workflows/support/graph.py`
- Create: `backend/src/app/workflows/support/nodes/input.py`
- Create: `backend/src/app/workflows/support/nodes/planner.py`
- Create: `backend/src/app/workflows/support/nodes/knowledge.py`
- Create: `backend/src/app/workflows/support/nodes/transaction.py`
- Create: `backend/src/app/workflows/support/nodes/response.py`
- Modify: `backend/src/app/workflows/support/nodes/__init__.py`
- Modify: `backend/src/app/runtime/container.py`
- Create: `backend/src/app/api/routes/support.py`
- Modify: `backend/src/app/api/app.py`
- Modify: `backend/src/app/schemas/api.py`
- Create: `backend/tests/unit/workflows/support/test_edges.py`
- Create: `backend/tests/integration/workflows/support/test_graph.py`
- Create: `backend/tests/e2e/api/test_support_api.py`
- Modify: `backend/tests/contract/test_langgraph_manifest.py`

**Interfaces:**
- Produces: `SupportState` v1 and `SupportGraphDependencies`
- Produces: deterministic edges and multi-node graph
- Produces: `POST /support/query` whose tenant and scopes come only from `RequestContext`

- [ ] **Step 1: 写入 state/edge RED 测试**

```python
class SupportState(TypedDict, total=False):
    graph_revision: str
    state_schema_version: int
    request: SupportRequest
    decision: PlannerDecision
    retrieval: RetrievalResult
    tool_results: Annotated[list[ToolExecutionResult], operator.add]
    transaction_evidence_ids: Annotated[tuple[str, ...], merge_evidence_ids]
    completed_steps: Annotated[list[str], operator.add]
    response: SupportResponse
    errors: Annotated[list[str], operator.add]
```

测试 edge 不修改 state，覆盖 clarification/refusal/escalation/knowledge/transaction/mixed/sufficiency 路由。

`merge_evidence_ids(left, right)` 必须返回 `tuple(sorted(set(left) | set(right)))`，使并行 transaction 节点、重放和 checkpoint 恢复得到同一稳定结果；`guard_output` 调用时显式转换为 `frozenset(state["transaction_evidence_ids"])`。

同时在 `test_graph.py` 写入身份边界 RED：

```python
def test_validate_input_rejects_request_identity_not_bound_to_runtime(graph, request):
    forged = request.model_copy(
        update={"tenant_id": "tenant-b", "actor_permission_scopes": frozenset({"admin"})}
    )
    result = graph.invoke(
        initial_support_state(forged),
        config=thread_config("support-identity-mismatch"),
        context=graph_context(tenant_id="tenant-a", permissions=("support:policy",)),
    )
    assert result["response"].status == "escalated"
    assert result["errors"] == ["runtime_identity_mismatch"]


def test_transaction_evidence_survives_checkpoint_before_output_guard(
    container, initial_state, thread_config, graph_context, grounded_response
):
    paused_graph = build_support_graph(
        container, interrupt_before=("guard_output",)
    )
    paused_graph.invoke(initial_state, config=thread_config, context=graph_context)
    snapshot = paused_graph.get_state(thread_config)
    assert len(snapshot.values["transaction_evidence_ids"]) == 1
    allowed_id = snapshot.values["transaction_evidence_ids"][0]
    rebuilt_graph = build_support_graph(container)
    resumed = rebuilt_graph.invoke(None, config=thread_config, context=graph_context)
    assert resumed["transaction_evidence_ids"] == (allowed_id,)
    rejected = inspect_output(
        grounded_response.model_copy(update={"transaction_evidence_ids": ["sha256:" + "b" * 64]}),
        allowed_source_ids=frozenset(),
        transaction_evidence_ids=frozenset(snapshot.values["transaction_evidence_ids"]),
    )
    assert rejected.allowed is False
    assert "transaction_evidence_not_allowed" in rejected.reason_codes
```

`build_support_graph(container, *, interrupt_before: tuple[str, ...] = ())` 只把该参数传给 `compile()`，默认生产和 manifest 仍为空 tuple；测试用它在 `guard_output` 前制造真实 checkpoint，不通过手工伪造 state 绕过 reducer。

- [ ] **Step 2: 写入完整 graph RED 测试**

覆盖 mixed 两分支都执行、工具失败产生 partial、知识和工具都无证据升级、交易工具完成后到 output guard 前的 checkpoint/rebuild/resume round trip。流式 envelope 与 final 一致性由 Task 10 的 Harness/streaming 契约统一验证。

在 `test_support_api.py` 证明请求 body 不能授予身份：body schema 不含 `tenant_id`、`actor_permission_scopes`、`roles`、`permissions`；传入任一字段因 `extra="forbid"` 返回 422。正常请求由认证依赖的 `RequestContext.tenant_id` 和 `RequestContext.permissions` 构造 `SupportRequest`，测试通过 graph spy 断言实际入图值。

- [ ] **Step 3: 运行 RED**

Run: `python -m pytest tests/unit/workflows/support tests/integration/workflows/support -q`

Expected: FAIL，当前仍是单 answer wrapper。

- [ ] **Step 4: 实现图流**

```text
validate_input -> plan
  -> clarification/refusal/escalation -> guard_output -> END
  -> retrieve_knowledge -> optional execute_transaction_tools
  -> execute_transaction_tools
  -> assemble_evidence -> assess_evidence
  -> draft_or_partial/escalate -> guard_output -> END
```

节点依赖全部 build-time 注入；GraphRuntimeContext 提供身份；state 不保存 provider、secret、权限真源或未裁剪全文。

`validate_input` 必须在 planner/retriever/tool 之前比较 `SupportRequest.tenant_id == GraphRuntimeContext.tenant_id`，并要求 `SupportRequest.actor_permission_scopes <= frozenset(GraphRuntimeContext.permissions)`；任一不一致都返回 `runtime_identity_mismatch` 的无引用人工升级响应，且 planner、retriever、ToolExecutor 调用计数保持 0。`api/routes/support.py` 只接收无身份字段的 `SupportQueryBody`，从 `RequestContext` 构造完整 `SupportRequest`。

- [ ] **Step 5: 运行 GREEN、manifest、全量并提交**

Run: `python -m pytest tests/unit/workflows/support tests/integration/workflows/support tests/e2e/api/test_support_api.py tests/contract/test_langgraph_manifest.py -q`

Run: `python -m pytest -q`

```text
git diff --check
git commit -m "功能：实现标准客服 Routed RAG 工作流"
```

---

### Task 6: Provider-neutral Ports 与 Fake Provider

**Files:**
- Modify: `backend/src/app/configuration.py`
- Create: `backend/src/app/models/llm.py`
- Create: `backend/src/app/models/embeddings.py`
- Create: `backend/src/app/models/reranker.py`
- Create: `backend/src/app/models/vision.py`
- Create: `backend/src/app/models/providers/fake.py`
- Modify: `backend/src/app/runtime/container.py`
- Create: `backend/tests/unit/models/test_configuration.py`
- Create: `backend/tests/unit/models/test_fake_models.py`
- Modify: `backend/.env.example`

**Interfaces:**
- Produces: four provider-neutral ports and `ModelBundle`
- Produces: `build_model_bundle(settings)`

- [ ] **Step 1: 写入 SecretStr 与 profile RED 测试**

```python
def test_enabled_siliconflow_without_key_fails_fast():
    settings = Settings(MODEL_ENABLED=True, MODEL_PROVIDER="siliconflow", SILICONFLOW_API_KEY="")
    with pytest.raises(ModelConfigurationError, match="api_key_required"):
        build_model_bundle(settings)


def test_secret_repr_does_not_expose_value():
    synthetic = "secret-" + "value-123"
    settings = Settings(SILICONFLOW_API_KEY=synthetic)
    assert synthetic not in repr(settings)
    assert synthetic not in settings.model_dump_json()
```

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/unit/models -q`

Expected: FAIL，key 仍是普通 str 且 ports 不存在。

- [ ] **Step 3: 实现 ports 与 fake bundle**

定义 `LlmPort.generate`、`EmbeddingPort.embed`、`RerankerPort.rerank`、`VisionPort.analyze` 的严格 request/response models。`MODEL_ENABLED=false` 返回 None；provider=fake 返回记录调用数但不联网的 deterministic bundle；provider=siliconflow 缺 SecretStr fail fast。

`ApplicationContainer` 在本任务新增 `models: ModelBundle | None`，由 `create_application_container(settings)` 调用 `build_model_bundle(settings)` 注入；workflow/node 禁止自行读取 Settings 或构造 provider。

配置默认值固定为 `deepseek-ai/DeepSeek-V3.2`、`BAAI/bge-m3`、`BAAI/bge-reranker-v2-m3`、`Qwen/Qwen3-VL-32B-Instruct`，base URL 为 `https://api.siliconflow.cn/v1`。API key 字段使用 `SecretStr | None`，不得在 `model_dump`、repr、trace 或异常消息中输出原值。

- [ ] **Step 4: 更新空值 env example 并验证**

`.env.example` 中 key 为空，模型名固定为设计选择。Run: `python -m pytest tests/unit/models -q`。

- [ ] **Step 5: 提交**

```text
git diff --check
git commit -m "功能：增加模型端口与安全的 Fake Provider"
```

---

### Task 7: SiliconFlow Adapters

**Files:**
- Create: `backend/src/app/models/providers/siliconflow.py`
- Modify: `backend/pyproject.toml`
- Create: `backend/tests/unit/models/test_siliconflow.py`

**Interfaces:**
- Produces: `build_siliconflow_bundle(settings) -> ModelBundle`

- [ ] **Step 1: 写入无网络 RED 测试**

Stub `ChatOpenAI`、`OpenAIEmbeddings` 和 async reranker transport，断言 base_url、model、timeout、SecretStr 传递、响应映射和异常净化。任何未 stub transport 调用直接让测试失败。

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/unit/models/test_siliconflow.py -q`

Expected: FAIL，adapter 不存在。

- [ ] **Step 3: 实现 SiliconFlow bundle**

LLM/Vision 使用 OpenAI-compatible `ChatOpenAI`；Embedding 使用 `OpenAIEmbeddings`；Reranker 使用隔离的 injected httpx transport。业务层不返回 SDK 类型，不启动时探测网络。

- [ ] **Step 4: 添加依赖并验证**

在 pyproject 增加 `langchain-openai>=1.0,<2`。Run: `python -m pytest tests/unit/models -q`。

- [ ] **Step 5: 提交**

```text
git diff --check
git commit -m "功能：接入硅基流动模型适配器"
```

---

### Task 8: Canonical JSON v1 与统一评估产物

**Files:**
- Create: `backend/evals/common/canonical.py`
- Create: `backend/evals/common/models.py`
- Create: `backend/tests/unit/evals/test_canonical.py`
- Create: `backend/tests/contract/test_eval_artifact.py`

**Interfaces:**
- Produces: `canonical_json_v1`, `canonical_sha256_v1`, `seal_artifact`

- [ ] **Step 1: 写入规范化 RED 测试**

```python
def test_artifact_hash_excludes_only_its_own_field(unsealed_artifact):
    sealed = seal_artifact(unsealed_artifact)
    payload = sealed.model_dump(mode="json")
    digest = payload.pop("artifact_hash")
    assert digest == hashlib.sha256(canonical_json_v1(payload)).hexdigest()
```

覆盖 UTC 微秒 Z、Decimal 无指数和尾零、negative zero、Unicode key、None 保留、enum value、无序 path 排序、普通数组保序和 schema strict。

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/unit/evals/test_canonical.py tests/contract/test_eval_artifact.py -q`

Expected: FAIL，统一 canonical 模块不存在。

- [ ] **Step 3: 实现 canonical-json/v1**

输入先按 Pydantic schema 验证；递归规范化类型；JSON 使用 UTF-8、`ensure_ascii=False`、`sort_keys=True`、紧凑 separators。`artifact_hash` 计算时仅排除自身，started_at/duration 参与。

- [ ] **Step 4: 运行 GREEN 并提交**

Run: `python -m pytest tests/unit/evals/test_canonical.py tests/contract/test_eval_artifact.py -q`

```text
git diff --check
git commit -m "功能：增加可复现的评估产物封印"
```

---

### Task 9: 三套 Eval Runner 与统一 CLI

**Files:**
- Modify: `backend/evals/product_launch/runner.py`
- Create: `backend/evals/operations/__init__.py`
- Create: `backend/evals/operations/runner.py`
- Create: `backend/evals/operations/v1/cases.json`
- Create: `backend/evals/support/runner.py`
- Modify: `backend/evals/evaluators/support.py`
- Modify: `backend/evals/support/v1/cases.json`
- Create: `backend/evals/run_evals.py`
- Create: `backend/tests/integration/evals/test_eval_catalogs.py`
- Create: `backend/tests/integration/evals/test_eval_runners.py`
- Create: `backend/tests/e2e/test_eval_cli.py`

**Interfaces:**
- Produces: three `run_*_suite(container, dataset_path, clock) -> EvalArtifact`
- Produces: CLI `main(argv=None, *, container=None) -> int`

- [ ] **Step 1: 写入 suite catalog RED 测试**

Product 必须恰好 7 scenarios/8 metrics；Operations 恰好 7 类；Support 恰好 10 类且每类非空。重复、缺失、多余、空 metric/分母一律 raise gate error。

`test_eval_catalogs.py` 精确断言 Product 的七个既有 scenario ID、Operations 的 `healthy_control/low_stock/shipment_delay/conversion_drop/return_rate_rise/all_stale/tenant_or_version_conflict`、Support 的十个既有 category；`cases.json` 每条有唯一 `case_id/category/schema_version`，空 catalog 或 category count 为 0 必须失败。Operations runner 逐类精确断言 status、anomaly、evidence ID、proposal ID，并要求所有 proposal 的 `execution_allowed is False`。

- [ ] **Step 2: 写入 CLI RED 测试**

```python
def test_all_gate_returns_nonzero_when_any_suite_fails(tmp_path, failing_container):
    code = main(["--suite", "all", "--gate", "--output", str(tmp_path / "all.json")], container=failing_container)
    assert code == 1
    assert (tmp_path / "all.json").is_file()
```

- [ ] **Step 3: 运行 RED**

Run: `python -m pytest tests/integration/evals tests/e2e/test_eval_cli.py -q`

Expected: FAIL，Operations runner 和统一 CLI 不存在。

- [ ] **Step 4: 实现三套 gate**

Support 阈值：泄漏 0、citation >=0.95、no-answer >=0.90、injection 0、failed IDs 空、model calls/cost 0、p95 <=2000ms。Operations 精确匹配 7 类 status/anomaly/evidence/proposal，proposal 不可执行、tenant leak 0。Product 使用 7/8 和 canonical hash 精确门禁。

- [ ] **Step 5: 实现原子 JSON 输出**

CLI 写临时文件、fsync/replace 成目标；任何 suite 失败仍写脱敏 artifact 并返回 1；`all --gate` 聚合全部失败，不早退丢失诊断。

- [ ] **Step 6: 运行 GREEN 并提交**

Run: `python -m pytest tests/integration/evals tests/e2e/test_eval_cli.py -q`

```text
git diff --check
git commit -m "功能：增加三套离线评估与统一质量门禁"
```

---

### Task 10: Agent Harness、预算与流式运行基线

**Files:**
- Create: `backend/src/app/runtime/budgets.py`
- Create: `backend/src/app/runtime/rate_limits.py`
- Create: `backend/src/app/runtime/circuit_breakers.py`
- Create: `backend/src/app/runtime/harness.py`
- Modify: `backend/src/app/runtime/workflows.py`
- Create: `backend/src/app/schemas/streaming.py`
- Modify: `backend/src/app/configuration.py`
- Modify: `backend/src/app/runtime/container.py`
- Modify: `backend/src/app/api/routes/health.py`
- Modify: `backend/src/app/api/routes/workflows.py`
- Modify: `backend/src/app/api/routes/support.py`
- Create: `backend/tests/unit/runtime/test_budgets.py`
- Create: `backend/tests/unit/runtime/test_harness.py`
- Create: `backend/tests/integration/runtime/test_harness.py`
- Create: `backend/tests/integration/runtime/test_native_product_launch_harness.py`
- Create: `backend/tests/contract/test_streaming_events.py`
- Create: `backend/tests/e2e/api/test_streaming.py`
- Modify: `backend/tests/e2e/test_product_launch_hitl.py`
- Modify: `backend/tests/e2e/api/test_health.py`
- Create: `docs/runbooks/agent-runtime.md`
- Create: `docs/runbooks/agent-runtime-rollback.md`

**Interfaces:**
- Produces: `ExecutionBudget`
- Produces: `AgentHarness.admit/run/run_native/stream/cancel`
- Produces: `TenantRateLimiter` and `ProviderCircuitBreaker`
- Produces: `StreamEvent` with `trace/status/delta/citation/final/error`

- [ ] **Step 1: 写入预算和取消 RED 测试**

```python
async def test_harness_stops_before_model_call_budget_is_exceeded(harness, model_spy):
    budget = ExecutionBudget(max_model_calls=1, max_tool_calls=3, max_iterations=4)
    result = await harness.run("support", request_requiring_two_model_calls(), budget=budget)
    assert result.status == "budget_exceeded"
    assert result.error_code == "max_model_calls_exceeded"
    assert model_spy.calls == 1


async def test_cancel_is_tenant_scoped_and_cooperative(harness, running_execution):
    assert await harness.cancel(
        running_execution.run_id,
        tenant_id="tenant-b",
        subject_id="operator-b",
    ) is False
    assert await harness.cancel(
        running_execution.run_id,
        tenant_id="tenant-a",
        subject_id="operator-a",
    ) is True


async def test_product_start_and_resume_use_harness_without_bypassing_fencing(
    workflow_service, harness_spy, approved_workflow
):
    await workflow_service.start(
        workflow_command(), request_context(), idempotency_key="create-1"
    )
    await workflow_service.resume(
        approved_workflow.workflow_id,
        approved_workflow.approval_id,
        request_context(),
    )
    assert [call.method for call in harness_spy.calls] == [
        "admit", "run_native", "admit", "run_native"
    ]
    assert all(call.config["configurable"]["thread_id"] for call in harness_spy.native_calls)
    assert harness_spy.native_calls[1].input.command == "resume"
```

参数化验证总超时、单步骤超时、`max_model_calls`、`max_tool_calls`、`max_iterations`、`max_cost_usd`；预算耗尽必须在下一次副作用前 fail closed，并产生脱敏 trace。

- [ ] **Step 2: 写入 streaming、限流、熔断和 readiness RED 测试**

```python
def test_stream_event_type_is_closed_set():
    assert set(get_args(StreamEventType)) == {
        "trace", "status", "delta", "citation", "final", "error"
    }


async def test_stream_final_equals_non_stream_response(harness, command, context):
    direct = await harness.run("support", command, context=context)
    events = [event async for event in harness.stream("support", command, context=context)]
    final = next(event for event in events if event.type == "final")
    assert final.data == direct.response.model_dump(mode="json")
```

同一 graph 和同一 `ExecutionBudget` 驱动 run/stream；tenant rate limit 在图执行前拒绝，provider circuit breaker 只包 provider port，open 状态不阻断 deterministic baseline。readiness 测试断言 checkpointer/store/ledger 依赖可用且 production profile 不允许 memory durability。

- [ ] **Step 3: 运行 RED**

Run: `python -m pytest tests/unit/runtime/test_budgets.py tests/unit/runtime/test_harness.py tests/integration/runtime/test_harness.py tests/integration/runtime/test_native_product_launch_harness.py tests/contract/test_streaming_events.py tests/e2e/api/test_streaming.py tests/e2e/api/test_health.py tests/e2e/test_product_launch_hitl.py -q`

Expected: FAIL，统一 Harness、预算和封闭流式 envelope 尚不存在。

- [ ] **Step 4: 实现 Harness 与生产保护面**

```python
class ExecutionBudget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    total_timeout_seconds: float = Field(default=30, gt=0, le=300)
    step_timeout_seconds: float = Field(default=10, gt=0, le=120)
    max_model_calls: int = Field(default=4, ge=0, le=32)
    max_tool_calls: int = Field(default=12, ge=0, le=128)
    max_iterations: int = Field(default=16, ge=1, le=256)
    max_cost_usd: Decimal = Field(default=Decimal("0.50"), ge=0)
```

`AgentHarness` 是 API/CLI 调图的唯一入口：根据 graph ID 从 `GraphRegistry` 取图，绑定 `GraphRuntimeContext`、预算计数器、deadline 和 cancellation token；`admit()` 在任何 workflow claim 前完成 tenant rate limit、budget validation 和 cancellation registration并返回一次性 `HarnessAdmission`；`run()` 返回最终 DTO，`run_native(admission, graph_input, config, context)` 保留 LangGraph thread config 和 `Command(resume=...)`，`stream()` 只投影封闭事件类型并保证唯一 final/error 终止事件，`cancel()` 强制 tenant/subject 权限。所有 model/tool 调用分别在 port/executor 边界计数，禁止依赖节点自报。

本任务必须修改 `ProductLaunchWorkflowService`：start/resume 开头先调用 `harness.admit()`，成功后才执行 `create_or_get/claim_run`；其 `_invoke_claimed` 将直接 `self._graph.ainvoke` 替换为 `harness.run_native()`。claim/fencing、thread_id、Approval decision、`RuntimeUnitOfWork.record_pause` 和 `complete_run` 仍由 workflow service 管理，Harness 不复制业务恢复逻辑。admission/预算/限流失败发生在 claim 前；run_native 超时、取消或 provider 失败继续走 service 的 failed/cancelled fencing finalize。E2E 断言限流返回 429 时 graph/claim 计数均为 0，重复 idempotency key 仍只执行一次图，resume 保留同一 thread 且发布 ledger 不重复调用 adapter。

`TenantRateLimiter` 的 memory 实现只用于单进程 MVP；`ProviderCircuitBreaker` 使用 closed/open/half_open 状态和 injected clock。`/health/live` 只证明进程存活，`/health/ready` 检查 saver/store/workflow ledger/publish ledger 和 provider circuit 状态，并公开 `durability_profile`，不回显 DSN、key 或内部 checkpoint ID。

- [ ] **Step 5: 编写运行与回滚手册**

`agent-runtime.md` 固定记录预算默认值、告警指标、限流/熔断恢复、unknown publish reconciliation、取消语义和 memory profile 仅支持单进程 MVP；`agent-runtime-rollback.md` 给出关闭模型、停止新流量、等待/取消活跃 run、对账 unknown publish、回滚应用版本、验证旧 graph revision 和恢复流量的顺序及命令。

- [ ] **Step 6: 运行 GREEN、全量、格式检查并提交**

Run: `python -m pytest tests/unit/runtime tests/integration/runtime tests/contract/test_streaming_events.py tests/e2e/api/test_streaming.py tests/e2e/api/test_health.py tests/e2e/test_product_launch_hitl.py -q`

Run: `python -m pytest -q`

Run from repository root: `git diff --check`

```text
git commit -m "功能：增加 Agent Harness 预算流式与运行保护"
```

---

### Task 11: Privacy-safe Secret Scanner

**Files:**
- Create: `backend/scripts/scan_secrets.py`
- Create: `backend/tests/unit/scripts/test_scan_secrets.py`
- Modify: `.gitignore`
- Modify: `backend/.gitignore`

**Interfaces:**
- Produces: `scan_repository(repo, options) -> ScanReport`
- Produces: CLI `main(argv=None) -> int`

- [ ] **Step 1: 写入 staged/history/example RED 测试**

在 tmp git repo 中动态拼接合成 `sk-`、PEM、AWS token，分别写入 tracked、staged、提交后删除和 `.env.example` 非空变量；断言均被发现。断言报告不含完整值，只含 path/line/rule/length/hash prefix。

- [ ] **Step 2: 写入隐私边界 RED 测试**

证明 scanner 不读取 untracked `.env`、不读取进程环境、不扫描 ignored eval runtime artifacts。

- [ ] **Step 3: 运行 RED**

Run: `python -m pytest tests/unit/scripts/test_scan_secrets.py -q`

Expected: FAIL，scanner 不存在。

- [ ] **Step 4: 实现 Git 范围扫描**

使用参数化 subprocess 调用 git ls-files、git diff --cached、git merge-base 和 git log/diff range；检查新增和删除行。`.env.example` 中 KEY/TOKEN/SECRET/PASSWORD 必须为空或 `${ENV_VAR}` 引用。

- [ ] **Step 5: 运行 GREEN 并提交**

Run: `python -m pytest tests/unit/scripts/test_scan_secrets.py -q`

```text
git diff --check
git commit -m "安全：增加受控历史与暂存凭据扫描"
```

---

### Task 12: CI 契约与最终门禁

**Files:**
- Modify: `.github/workflows/backend-ci.yml`
- Modify: `backend/README.md`
- Create: `backend/tests/contract/test_ci_contract.py`
- Modify: `docs/progress/2026-07-14-langgraph-standard-runtime-integration.md`

- [ ] **Step 1: 写入 CI RED 契约**

解析 workflow，断言 checkout `fetch-depth: 0`、Python 3.12、MODEL_ENABLED=false、MODEL_PROVIDER=fake；步骤顺序包含 secret scan、compileall、全量 pytest、manifest、三套单跑和 all gate；不得设置真实 key。

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/contract/test_ci_contract.py -q`

Expected: FAIL，CI 尚无完整门禁。

- [ ] **Step 3: 实现 CI 与 artifacts**

任一步非零立即阻断；artifact upload path 精确列出 `backend/outputs/evals/product-launch-v1.json`、`backend/outputs/evals/operations-v1.json`、`backend/outputs/evals/support-v1.json`、`backend/outputs/evals/all-v1.json` 和 `backend/outputs/security/secret-scan.json`。README 命令必须与 CI 一致。

- [ ] **Step 4: 执行最终验证**

From `backend/`:

```text
python -m compileall -q src/app
python -m pytest -q
python -m pytest tests/contract/test_langgraph_manifest.py -q
python evals/run_evals.py --suite product_launch --output outputs/evals/product-launch-v1.json
python evals/run_evals.py --suite operations --output outputs/evals/operations-v1.json
python evals/run_evals.py --suite support --output outputs/evals/support-v1.json
python evals/run_evals.py --suite all --gate --output outputs/evals/all-v1.json
```

From repository root:

```text
git diff --check
python backend/scripts/scan_secrets.py --tracked --staged --history-base origin/main --env-example backend/.env.example
```

Expected: 全部 exit 0，Support model calls/cost 为 0，scanner findings 为空。

- [ ] **Step 5: 提交、独立评审并推送**

```text
git commit -m "持续集成：增加三图安全与质量发布门禁"
git push -u origin dev-com
```

在 progress log 追加唯一一行 `QUALITY_FINAL_SHA=` 与当前 `git rev-parse HEAD` 的 40 位小写值，并记录测试数量、四份评估 artifact hash、scanner 结论和 reviewer 结论。请求独立 reviewer 对完整规范、四份计划、最终 diff 和验证产物进行 requirements audit；Critical/Important 全部关闭后只推送 `dev-com`，禁止合并 `main`。
