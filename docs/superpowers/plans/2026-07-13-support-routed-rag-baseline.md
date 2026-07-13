# Node 19 客服 Routed RAG Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立客服 Routed RAG 证据基线：实时交易问题返回工具需求，静态知识经过 tenant/ACL 预过滤、词法检索和真实引用生成回复草稿。

**Architecture:** 采用一次确定性 Planner、一次词法检索、一次上下文装配，不使用向量库、reranker、LLM 或 evaluator/refiner loop。内存索引实现摄取与检索端口，未来 pgvector/Qdrant 只替换端口实现。

**Tech Stack:** Python 3.12, Pydantic 2.11.7, pytest 8.4.1, standard-library lexical inverted index.

## Global Constraints

- 分支：`codex/node-19-support-rag`，基线必须包含提交 `5cc8bc5`。
- 只创建 `backend/app/domain/support.py`、`backend/app/rag/support/`、`backend/app/mock_data/support_kb/`、`backend/evals/support/`、`backend/tests/test_support_rag.py` 和 Node 19 进度日志。
- 禁止修改 `backend/app/main.py`、`backend/app/agents/profiles.py`、`backend/app/agents/graphs/state.py`、公共路由和 `backend/app/tools/registry.py`。
- 只读复用 `app.config.models.RETRIEVAL_CONFIG` 中 `initial_top_k=20`、`score_threshold=0.3`；不使用 max refinements、embedding 或 reranker。
- 所有状态和结果携带 `tenant_id`。文档 ACL 规则：`source.permission_scopes` 必须是 actor scopes 的子集；空集合表示公开。
- `parent_id` 只保留，不做父文档扩展。交易 route 只声明工具需求，由 Node 20 接线执行。
- trace summary 只保留 ID、版本、数量、分数、决策和错误类别，不保留 query、chunk 正文或完整响应。
- 检索内容是不可信数据，不得改变 route、filters、tools 或 security policy。
- 默认测试不调用真实 SiliconFlow、embedding、reranker、向量库或外部服务。
- Git 提交描述使用中文。
- 执行时同时遵守 agentic-rag 和 agentic-rag-production；所有 pytest 命令从 `backend/` 执行，解释器固定为 `C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`。

---

## Files

- Create: `backend/app/domain/support.py`
- Create: `backend/app/rag/support/__init__.py`
- Create: `backend/app/rag/support/ports.py`
- Create: `backend/app/rag/support/planner.py`
- Create: `backend/app/rag/support/lexical.py`
- Create: `backend/app/rag/support/context.py`
- Create: `backend/app/rag/support/safety.py`
- Create: `backend/app/rag/support/service.py`
- Create: `backend/app/rag/support/evaluation.py`
- Create: `backend/app/mock_data/support_kb/__init__.py`
- Create: `backend/app/mock_data/support_kb/loader.py`
- Create: `backend/app/mock_data/support_kb/corpus.json`
- Create: `backend/evals/support/v1/cases.json`
- Create: `backend/tests/test_support_rag.py`
- Create: `docs/progress/2026-07-13-node-19-support-rag.md`

## Frozen Interfaces

All contracts use `ConfigDict(extra="forbid", frozen=True)`. Hash format is `sha256:<64 lowercase hex>`. Datetimes must be timezone-aware. A locator must include a URI and at least one real page, section, row or timestamp position.

```python
class SourceLocator(SupportContract):
    uri: str
    page: int | None
    section_path: tuple[str, ...]
    row: int | None
    timestamp: datetime | None


class SupportSource(SupportContract):
    source_id: str
    tenant_id: str
    title: str
    document_type: SupportDocumentType
    marketplace: SupportMarketplace | None
    locale: str
    product_id: str | None
    permission_scopes: frozenset[str]
    policy_version: str | None
    authority: SupportAuthority
    effective_from: datetime | None
    effective_to: datetime | None
    content_hash: str
    index_version: str
    locator: SourceLocator
    status: Literal["active", "tombstoned"]


class SupportChunk(SupportContract):
    chunk_id: str
    parent_id: str | None
    source_id: str
    tenant_id: str
    text: str
    permission_scopes: frozenset[str]
    marketplace: SupportMarketplace | None
    locale: str
    product_id: str | None
    policy_version: str | None
    authority: SupportAuthority
    effective_from: datetime | None
    effective_to: datetime | None
    content_hash: str
    index_version: str
    locator: SourceLocator


class SupportRequest(SupportContract):
    trace_id: str
    tenant_id: str
    ticket_id: str
    query: str
    actor_permission_scopes: frozenset[str]
    marketplace: SupportMarketplace
    locale: str
    product_id: str | None
    sku: str | None
    effective_at: datetime


class PlannerDecision(SupportContract):
    trace_id: str
    tenant_id: str
    intent: SupportIntent
    route: Literal["lexical_retrieval", "requires_transaction_tool", "off_topic", "escalate"]
    filters: RetrievalFilters
    transaction_request: TransactionToolRequest | None
    reason_code: str


class RetrievalResult(SupportContract):
    trace_id: str
    tenant_id: str
    status: Literal["ok", "unavailable"]
    candidates: tuple[RetrievalCandidate, ...]
    index_version: str
    eligible_count: int
    stale_filtered_count: int
    failure_code: str | None


class SupportResponse(SupportContract):
    trace_id: str
    tenant_id: str
    status: Literal["draft", "requires_transaction_tool", "insufficient_evidence", "off_topic", "escalated"]
    draft: str
    citations: tuple[SupportCitation, ...]
    transaction_request: TransactionToolRequest | None
    requires_human_review: bool
    reason_code: str
    trace: SupportTraceSummary
```

Ports and service:

```python
class SupportIngestionPort(Protocol):
    def ingest(self, source: SupportSource, chunks: Sequence[SupportChunk]) -> IngestionResult: ...
    def tombstone(self, *, tenant_id: str, source_id: str) -> IngestionResult: ...


class SupportRetriever(Protocol):
    def retrieve(self, request: RetrievalRequest) -> RetrievalResult: ...


class SupportPlanner(Protocol):
    def plan(self, request: SupportRequest) -> PlannerDecision: ...


def assemble_context(result: RetrievalResult, *, max_chunks: int, max_chars: int) -> AssembledContext: ...


class SupportRagService:
    def answer(self, request: SupportRequest) -> SupportResponse: ...
```

### Task 1: Domain Contracts And Ports

**Files:** Create domain/ports/test.

- [x] **Step 1: Write RED tests** for page 0, invalid SHA-256, missing tenant/ACL, fake locator, naive datetime and response/retrieval tenant mismatch.
- [x] **Step 2: Verify RED**:

```powershell
& 'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m pytest tests/test_support_rag.py -k "contract or locator" -v
```

Expected: collection FAIL because contracts are absent.

- [x] **Step 3: Implement GREEN** with controlled Literal types, validators and the frozen interfaces above.
- [x] **Step 4: Verify and commit**; expected PASS. Commit: `feat: 定义客服 RAG 契约与扩展端口`.

### Task 2: Idempotent Ingestion And Tombstones

**Files:** Create lexical index; modify test.

- [x] **Step 1: Write RED tests** for idempotency by tenant/source/hash/index version, atomic version replacement, old chunk tombstones, tenant-scoped repeated tombstone and rejected weaker ACL/chunk hash mismatch.
- [x] **Step 2: Verify RED** with `pytest tests/test_support_rag.py -k "ingestion or tombstone" -v`; expected FAIL.
- [x] **Step 3: Implement GREEN**. Index active source by `(tenant_id, source_id)`; same hash/version -> `skipped`; new version atomically replaces active chunks; duplicate tombstone -> `skipped`; bad metadata -> stable failed result.
- [x] **Step 4: Verify and commit**; expected PASS. Commit: `feat: 实现客服知识幂等摄取`.

### Task 3: Deterministic Planner And Transaction Route

**Files:** Create planner/service; modify test.

- [x] **Step 1: Write RED parameterized tests** for order status, shipment trajectory, payment status, refund amount, inventory, coupon and ticket history as transaction routes; refund policy/shipping SLA as RAG; off-topic refusal; legal threat escalation; non-RAG routes must not invoke retriever.
- [x] **Step 2: Verify RED** with `pytest tests/test_support_rag.py -k "planner or transaction or off_topic" -v`; expected FAIL.
- [x] **Step 3: Implement GREEN**. `RuleBasedSupportPlanner.plan()` only creates intent/route/filter/reason. `refund policy` must not match the `refund amount` route. Transaction route returns `requires_transaction_tool` without reading the tool registry.
- [x] **Step 4: Verify and commit**; expected PASS. Commit: `feat: 增加客服问题确定性路由`.

### Task 4: ACL-Prefiltered Lexical Retrieval And Citations

**Files:** Modify lexical; create context; modify test.

- [x] **Step 1: Write RED tests** proving tenant/ACL filters run before scoring, filters include marketplace/locale/product/effective time, index is built at ingestion rather than per request, context dedupes/budgets/preserves locators and citations exactly match used blocks.
- [x] **Step 2: Verify RED** with `pytest tests/test_support_rag.py -k "retrieval or context or citation" -v`; expected FAIL.
- [x] **Step 3: Implement GREEN**. Maintain inverted postings during ingestion. Filter allowed chunk IDs before lexical scoring. Assemble at most 5 chunks/4000 chars, dedupe by source/parent/text hash, render `[n]` evidence blocks and one-to-one citations.
- [x] **Step 4: Verify and commit**; expected PASS. Commit: `feat: 增加 ACL 词法检索与引用上下文`.

### Task 5: No-Answer, Stale, Injection And Failure Handling

**Files:** Create safety; modify service/test.

- [x] **Step 1: Write RED tests** for ACL denial indistinguishable from empty corpus, stale-only evidence, injected document attempting to alter system/tool/filter/citation, safe neighbor survival, index unavailable and exactly one retrieval with no refinement loop.
- [x] **Step 2: Verify RED** with `pytest tests/test_support_rag.py -k "insufficient or stale or injection or unavailable or refinement" -v`; expected FAIL.
- [x] **Step 3: Implement GREEN**. Unsafe chunks never enter context. Empty/ACL -> generic `insufficient_evidence`; stale -> `stale_evidence`; outage -> `escalated/retrieval_unavailable`; all require human review and have no citations.
- [x] **Step 4: Verify and commit**; expected PASS. Commit: `fix: 阻断客服 RAG 过期与注入证据`.

### Task 6: Mock Corpus And Security Evaluation Set

**Files:** Create corpus loader, JSON corpus, eval cases/evaluator; modify test.

- [x] **Step 1: Write RED tests** for a ten-case catalog: product fact, current return policy, marketplace isolation, transaction route, no-answer, off-topic, same-tenant ACL denial, cross-tenant denial, stale policy, prompt injection.
- [x] **Step 2: Verify RED** with `pytest tests/test_support_rag.py -k "corpus or eval or quality_gate" -v`; expected FAIL.
- [x] **Step 3: Implement GREEN**. Loader uses real `mock://...#section` locators. Deterministic evaluator computes permission leak rate, citation precision, no-answer accuracy and prompt-injection success rate with failed case IDs; no LLM judge.
- [x] **Step 4: Quality gates**: permission leak `== 0`; citation precision `>= 0.95`; no-answer accuracy `>= 0.90`; injection success `== 0`.
- [x] **Step 5: Verify and commit**; expected PASS. Commit: `test: 增加客服 RAG 安全评估基线`.

### Task 7: Progress Log And Verification

**Files:** Create progress log.

- [x] Run focused `pytest tests/test_support_rag.py -v`.
- [x] Run full `pytest -v`, compile check and repository-root `git diff --check`.
- [x] Request independent review against shared design, PRD sections 7.11/15.3 and production RAG security/evaluation requirements; resolve every Critical/Important issue. 当前环境未暴露独立子 Agent 工具，限制已写入进度日志，并以完整 branch diff 对照审查补充验证。
- [x] Write Chinese log with contracts, ingestion lifecycle, route matrix, ACL/injection defense, eval gates, real test counts and Node 20 boundary.
- [x] Confirm branch diff contains only Node 19 owned paths.
- [x] Commit and push: `docs: 记录第十九节点客服 RAG 实现进度`; `git push -u origin codex/node-19-support-rag`.
