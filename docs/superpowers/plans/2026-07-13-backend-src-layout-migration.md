# Backend Src 标准工程迁移实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将四节点集成后的后端原子迁移到 `backend/src/app/`，按参考示例建立标准模块、三张可导出图、依赖注入和分层测试，不保留旧 import 兼容层。

**Architecture:** 先建立 `pyproject.toml` 和项目布局契约，再进行行为不变的 src-root 移动；随后按公共模块和工作流职责拆分。默认 `ApplicationContainer` 共享一个 InMemorySaver/Store 和仓储实例，模块级 graph 只编译一次；原生 HITL 行为留给下一计划。

**Tech Stack:** Python 3.12, Hatchling, FastAPI 0.116.1, Pydantic 2.11.7, LangGraph 1.2.9, pytest 8.4.1.

## Global Constraints

- 执行分支：`dev-com`，必须已完成前一计划并包含修复后的 Node 16-19。
- 开始本计划前，从 progress log 唯一提取 `NODE_INTEGRATION_SHA`，校验格式、Git 对象和祖先关系；使用下方命令，任一步非零立即停止。
- 本计划禁止合并或推送 `main`。
- 先验证四个节点聚焦测试和全量测试；任何失败都不能开始移动。
- Python import 根始终是 `app`；禁止 `src.app`、`backend.src.app` 和手工修改 `sys.path`。
- 最终删除 `backend/app/`、`backend/requirements.txt`、旧 `agents/`、`config/`、`repositories/`、`security/`；不得创建 re-export 兼容层。
- graph 文件只装配，state 只保存可序列化状态，edges 只路由，nodes 只返回增量。
- 生产包禁止 import `evals`；evals 可以 import `app`。
- 包内资源使用 `importlib.resources`，不使用依赖目录层数的 `parents[n]`。
- 每个结构任务独立提交；纯移动与行为修改不得混在同一提交。
- 所有复杂结构迁移说明和运行时边界使用必要中文注释；Git 提交使用中文。

```powershell
$progressPath = "docs/progress/2026-07-14-langgraph-standard-runtime-integration.md"
$shaLines = @(Get-Content -Encoding UTF8 $progressPath | Where-Object {
    $_ -match '^NODE_INTEGRATION_SHA=[0-9a-f]{40}$'
})
if ($shaLines.Count -ne 1) { throw "NODE_INTEGRATION_SHA must appear exactly once" }
$nodeIntegrationSha = $shaLines[0].Split('=', 2)[1]
git cat-file -e ($nodeIntegrationSha + "^{commit}")
if ($LASTEXITCODE -ne 0) { throw "NODE_INTEGRATION_SHA is not a commit" }
git merge-base --is-ancestor $nodeIntegrationSha HEAD
if ($LASTEXITCODE -ne 0) { throw "NODE_INTEGRATION_SHA is not an ancestor" }
```

---

### Task 1: Pyproject 与目录契约

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/tests/contract/test_project_layout.py`
- Create: `backend/src/app/__init__.py`

**Interfaces:**
- Produces: a single installable package `app`
- Produces: pytest paths and markers

- [ ] **Step 1: 写入项目布局 RED 测试**

```python
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def test_backend_uses_single_src_package_and_dependency_manifest():
    assert (BACKEND_ROOT / "pyproject.toml").is_file()
    assert (BACKEND_ROOT / "src/app/__init__.py").is_file()


@pytest.mark.xfail(reason="Task 8 retires the legacy package", strict=True)
def test_legacy_package_and_requirements_are_retired():
    assert not (BACKEND_ROOT / "app").exists()
    assert not (BACKEND_ROOT / "requirements.txt").exists()
```

仅在 Task 8 退役旧路径时删除 `xfail` marker；不得长期保留 xfail。

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/contract/test_project_layout.py -q`

Expected: FAIL，缺 `pyproject.toml` 和 src package。

- [ ] **Step 3: 创建 pyproject**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "eshop-agent-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi==0.116.1",
  "uvicorn[standard]==0.35.0",
  "pydantic==2.11.7",
  "pydantic-settings==2.10.1",
  "httpx==0.28.1",
  "python-dotenv==1.1.1",
  "langgraph==1.2.9",
]

[project.optional-dependencies]
dev = ["pytest==8.4.1"]
production = ["langgraph-checkpoint-postgres>=3.1,<4"]

[tool.hatch.build.targets.wheel]
packages = ["src/app"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "-q -m 'not external'"
markers = [
  "integration: in-process integration tests",
  "e2e: API and workflow end-to-end tests",
  "external: tests requiring real external services",
]
```

- [ ] **Step 4: 安装 editable package 并验证 GREEN**

Run: `python -m pip install -e ".[dev]"`

Run: `python -m pytest tests/contract/test_project_layout.py -q`

Expected: 仅两个退役断言处于明确 xfail，其余 PASS。

- [ ] **Step 5: 提交**

```text
git diff --check
git commit -m "构建：建立后端 src 工程与依赖清单"
```

---

### Task 2: 原子移动到 src 根

**Files:**
- Move directory: `backend/app` to `backend/src/app`
- Modify: `backend/src/app/agents/evaluation/runner.py`
- Modify: `backend/src/app/mock_data/support_kb/loader.py`
- Modify: `backend/src/app/services/operations.py`
- Modify: `backend/tests/test_product_launch_golden.py`
- Modify: `backend/tests/test_operations_agent.py`
- Modify: `backend/tests/test_support_rag.py`

**Interfaces:**
- Preserves: all existing `app.*` imports and behavior

- [ ] **Step 1: 记录移动前测试基线**

Run: `python -m pytest -q`

Expected: PASS；记录真实数量。

- [ ] **Step 2: 使用 Git 原子移动**

移动整个 `backend/app` 到 `backend/src/app`，合并已创建的 `src/app/__init__.py`。本步骤不重命名内部模块、不拆函数、不修改业务逻辑。

- [ ] **Step 3: 修复资源定位而非 import**

Operations mock data 改为：

```python
from importlib.resources import files

DATA_ROOT = files("app.mock_data.operations")
```

Product Launch/Support eval root 通过 runner 参数或测试 fixture 显式传入，不依赖 `Path(__file__).parents[n]`。

- [ ] **Step 4: 验证行为不变**

Run: `python -m compileall -q src/app`

Run: `python -m pytest -q`

Expected: 与移动前相同数量 PASS。

- [ ] **Step 5: 提交纯移动**

```text
git diff --check
git add -A backend/app backend/src/app
git commit -m "重构：原子迁移后端源码到 src 根"
```

---

### Task 3: 公共模块标准化

**Files:**
- Create: `backend/src/app/configuration.py`
- Create: `backend/src/app/guardrails/input_guard.py`
- Create: `backend/src/app/persistence/checkpointer.py`
- Create: `backend/src/app/persistence/store.py`
- Move: `backend/src/app/repositories/approvals.py` to `backend/src/app/persistence/repositories/approvals.py`
- Move: `backend/src/app/repositories/events.py` to `backend/src/app/persistence/repositories/trace_events.py`
- Move: `backend/src/app/repositories/snapshots.py` to `backend/src/app/persistence/repositories/semantic_checkpoints.py`
- Move: `backend/src/app/agents/observability/schema.py` to `backend/src/app/observability/schema.py`
- Move: `backend/src/app/agents/prompts/registry.py` to `backend/src/app/prompts/registry.py`
- Move: `backend/src/app/agents/mcp/registry.py` to `backend/src/app/adapters/mcp_registry.py`
- Move: `backend/src/app/agents/skills/registry.py` to `backend/src/app/tools/skills.py`
- Move: `backend/src/app/agents/profiles.py` to `backend/src/app/tools/profiles.py`
- Create: `backend/src/app/runtime/context.py`
- Create: `backend/src/app/runtime/container.py`
- Create: `backend/tests/unit/persistence/test_store_namespaces.py`
- Modify: `backend/tests/test_agent_boundaries.py`
- Modify: `backend/tests/test_agent_engineering_contract.py`
- Modify: `backend/tests/test_config.py`
- Modify: `backend/tests/test_langgraph_contract.py`
- Modify: `backend/tests/test_security_isolation.py`
- Modify: `backend/tests/test_trace_events.py`

**Interfaces:**
- Produces: `RequestContext`, `GraphRuntimeContext`
- Produces: `ApplicationContainer`, `create_application_container()`, `get_application_container()`
- Produces: shared checkpointer/store factories
- Produces: `StoreNamespacePolicy`

- [ ] **Step 1: 写入容器和 context RED 测试**

```python
def test_test_containers_are_isolated():
    first = create_application_container()
    second = create_application_container()
    assert first is not second
    assert first.checkpointer is not second.checkpointer
    assert first.approvals is not second.approvals


def test_graph_runtime_context_rejects_blank_identity():
    with pytest.raises(ValueError):
        GraphRuntimeContext(
            tenant_id=" ", subject_id="subject", roles=(), permissions=(),
            trace_id="trace", run_id="run",
        )


def test_production_profile_without_postgres_dsn_fails_fast():
    settings = Settings(RUNTIME_PROFILE="production", POSTGRES_DSN=None)
    with pytest.raises(ConfigurationError, match="postgres_dsn_required"):
        create_application_container(settings=settings)


def test_tenant_namespace_cannot_be_selected_by_payload(namespace_policy, context):
    namespace = namespace_policy.tenant_memory(context)
    key = namespace_policy.tenant_memory_key("customer_support", "preferences")
    assert namespace == ("tenant", context.tenant_id, "commerce_memory")
    assert key == "customer_support:preferences"


def test_global_playbook_write_requires_admin(namespace_policy, support_context):
    assert namespace_policy.global_playbooks() == ("global", "playbooks")
    with pytest.raises(PermissionError, match="global_playbook_admin_required"):
        namespace_policy.authorize_global_playbook_write(
            support_context, playbook_key="support-refund-v1"
        )
```

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/unit/runtime tests/contract/test_project_layout.py -q`

Expected: FAIL，runtime modules 尚不存在。

- [ ] **Step 3: 实现不可变 context**

```python
@dataclass(frozen=True, slots=True)
class GraphRuntimeContext:
    tenant_id: str
    subject_id: str
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
    trace_id: str
    run_id: str

    def __post_init__(self) -> None:
        for name in ("tenant_id", "subject_id", "trace_id", "run_id"):
            if not getattr(self, name).strip():
                raise ValueError(f"{name} must not be blank")
```

- [ ] **Step 4: 实现应用容器**

```python
@dataclass(frozen=True, slots=True)
class ApplicationContainer:
    checkpointer: BaseCheckpointSaver
    store: BaseStore
    approvals: ApprovalRepository
    semantic_checkpoints: SemanticCheckpointRepository
    traces: TraceEventRepository
    tool_registry: ToolRegistry
    tool_handlers: ToolHandlerCatalog
    tool_executor: ToolExecutor
    support_transactions: InMemorySupportTransactionAdapter
    support_retriever: InMemoryLexicalSupportIndex
    support_service: SupportRagService
```

`create_application_container()` 每次创建隔离实例；`get_application_container()` 只为默认 app 使用 `lru_cache(maxsize=1)`。节点不得调用 container getter，依赖由 `build_graph(container)` 注入。

`build_checkpointer(settings)` 和 `build_store(settings)` 在 memory profile 返回 InMemorySaver/InMemoryStore；production profile 延迟导入 PostgreSQL 实现并要求非空 DSN，缺配置时在创建 container 阶段 fail fast，不静默回退内存。

`StoreNamespacePolicy` 固定 tenant memory namespace 为 `("tenant", tenant_id, "commerce_memory")`，调用方不能传入 tenant namespace；agent role 和 memory 名称编码为 Store key。global playbook namespace 固定为 `("global", "playbooks")`，playbook ID 作为 key，仅 `roles` 含 `platform_admin` 的 `RequestContext` 可写。读取 global playbook 时按 `AgentProfile.allowed_playbooks` 过滤，profile 未声明的 key 在进入节点上下文前移除。测试覆盖跨 tenant 读写、普通客服写 global、未知 playbook key、管理员写入和 profile 过滤。

- [ ] **Step 5: 按 move map 清理旧公共目录**

固定映射：

| 来源 | 目标 |
|---|---|
| `src/app/config/settings.py` + `src/app/config/models.py` | `src/app/configuration.py` |
| `src/app/security/boundary.py` 的授权决策 | `src/app/tools/policy.py` |
| `src/app/security/boundary.py` 的 secret 检查 | `src/app/guardrails/input_guard.py` |
| `src/app/agents/profiles.py` | `src/app/tools/profiles.py` |
| `src/app/agents/checkpoints/policy.py` | `src/app/persistence/checkpointer.py` |
| `src/app/agents/memory/policy.py` | `src/app/persistence/store.py` |
| `src/app/agents/prompts/registry.py` | `src/app/prompts/registry.py` |
| `src/app/agents/mcp/registry.py` | `src/app/adapters/mcp_registry.py` |
| `src/app/agents/skills/registry.py` | `src/app/tools/skills.py` |
| `src/app/agents/graphs/nodes/base.py` | `src/app/schemas/runtime.py` |
| `src/app/domain/schemas.py` | `src/app/domain/listings.py` |
| `src/app/rag/support/safety.py` | `src/app/guardrails/retrieved_content_guard.py` |

完成 import 更新后删除空的 `config/`、`repositories/`、`security/` 以及已迁空的 `agents` 子目录。Evaluation 与 graph 子目录留给后续 Task 5/7 再迁，不在此步骤混入。

- [ ] **Step 6: 运行 GREEN、全量并提交**

Run: `python -m pytest tests/unit/runtime tests/unit/tools tests/integration/persistence -q`

Run: `python -m pytest -q`

```text
git diff --check
git commit -m "重构：建立应用容器与标准公共模块"
```

---

### Task 4: FastAPI 入口与依赖注入

**Files:**
- Move: `backend/src/app/main.py` to `backend/src/app/api/app.py`
- Create: `backend/src/app/api/dependencies.py`
- Create: `backend/src/app/schemas/api.py`
- Modify: `backend/src/app/api/routes/health.py`
- Modify: `backend/src/app/api/routes/agents.py`
- Modify: `backend/src/app/api/routes/approvals.py`
- Modify: `backend/src/app/api/routes/workflows.py`
- Modify: `backend/src/app/api/routes/marketplaces.py`
- Create: `backend/tests/conftest.py`
- Move: `backend/tests/test_health.py` to `backend/tests/e2e/api/test_health.py`
- Move: `backend/tests/test_agents_api.py` to `backend/tests/e2e/api/test_agents_api.py`
- Move: `backend/tests/test_approvals_api.py` to `backend/tests/e2e/api/test_approvals_api.py`
- Move: `backend/tests/test_workflows_api.py` to `backend/tests/e2e/api/test_workflows_api.py`

**Interfaces:**
- Produces: `create_app(container=None, graphs=None) -> FastAPI`
- Produces: request-scoped dependency functions
- Preserves: existing public route paths and response fields

- [ ] **Step 1: 写入 API 容器隔离 RED 测试**

```python
def test_two_apps_do_not_share_repositories():
    first_container = create_application_container()
    second_container = create_application_container()
    first = TestClient(create_app(container=first_container))
    second = TestClient(create_app(container=second_container))
    first.post("/workflows", json=workflow_payload())
    assert second.get("/approvals").json() == {"approvals": []}
```

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/e2e/api -k "do_not_share or dependencies" -q`

Expected: FAIL，当前 routes 使用模块级仓储 getter。

- [ ] **Step 3: 实现 app state 与 dependencies**

```python
def create_app(
    container: ApplicationContainer | None = None,
    graphs: GraphRegistry | None = None,
) -> FastAPI:
    app = FastAPI(title="Eshop Agent API", version="0.1.0")
    app.state.container = container or get_application_container()
    app.state.graphs = graphs or build_graph_registry(app.state.container)
    app.include_router(agents_router)
    app.include_router(approvals_router)
    app.include_router(health_router)
    app.include_router(marketplaces_router)
    app.include_router(workflows_router)
    return app
```

`api/dependencies.py` 只从 `request.app.state` 取依赖。开发 profile 的 demo identity header 明确隔离；生产 profile 禁止 demo provider。请求/响应 Pydantic model 从 routes 移到 `schemas/api.py`。

- [ ] **Step 4: 验证兼容 API**

Run: `python -m pytest tests/e2e/api -q`

Run: `python -m pytest -q`

Expected: PASS。

- [ ] **Step 5: 提交**

```text
git diff --check
git commit -m "重构：统一 FastAPI 入口与依赖注入"
```

---

### Task 5: 三个标准工作流包

**Files:**
- Create: `backend/src/app/workflows/product_launch/__init__.py`
- Create: `backend/src/app/workflows/product_launch/graph.py`
- Create: `backend/src/app/workflows/product_launch/state.py`
- Create: `backend/src/app/workflows/product_launch/edges.py`
- Create: `backend/src/app/workflows/product_launch/nodes/__init__.py`
- Create: `backend/src/app/workflows/product_launch/nodes/research.py`
- Create: `backend/src/app/workflows/product_launch/nodes/profit.py`
- Create: `backend/src/app/workflows/product_launch/nodes/suppliers.py`
- Create: `backend/src/app/workflows/product_launch/nodes/localization.py`
- Create: `backend/src/app/workflows/product_launch/nodes/listing.py`
- Create: `backend/src/app/workflows/product_launch/nodes/risk.py`
- Create: `backend/src/app/workflows/product_launch/nodes/approval.py`
- Create: `backend/src/app/workflows/product_launch/nodes/publish.py`
- Create: `backend/src/app/workflows/product_launch/nodes/completion.py`
- Create: `backend/src/app/workflows/operations/__init__.py`
- Create: `backend/src/app/workflows/operations/graph.py`
- Create: `backend/src/app/workflows/operations/state.py`
- Create: `backend/src/app/workflows/operations/edges.py`
- Create: `backend/src/app/workflows/operations/nodes/__init__.py`
- Create: `backend/src/app/workflows/operations/nodes/load.py`
- Create: `backend/src/app/workflows/operations/nodes/diagnose.py`
- Create: `backend/src/app/workflows/operations/nodes/propose.py`
- Create: `backend/src/app/workflows/operations/nodes/complete.py`
- Create: `backend/src/app/workflows/support/__init__.py`
- Create: `backend/src/app/workflows/support/graph.py`
- Create: `backend/src/app/workflows/support/state.py`
- Create: `backend/src/app/workflows/support/edges.py`
- Create: `backend/src/app/workflows/support/nodes/__init__.py`
- Create: `backend/src/app/workflows/support/nodes/answer.py`
- Create: `backend/src/app/runtime/graphs.py`
- Create: `backend/src/app/runtime/product_launch.py`
- Create: `backend/src/app/observability/recorders.py`
- Create: `backend/tests/contract/test_workflow_state_contracts.py`
- Modify: `backend/tests/test_product_launch_graph.py`
- Modify: `backend/tests/test_operations_agent.py`
- Modify: `backend/tests/test_support_rag.py`
- Modify: `backend/tests/test_langgraph_contract.py`

**Interfaces:**
- Produces: three `build_*_graph(container)` factories
- Produces: three module-level `graph` exports
- Produces: `GraphRegistry`

- [ ] **Step 1: 写入 graph module contract RED 测试**

```python
@pytest.mark.parametrize("graph_id", ["product_launch", "operations", "support"])
def test_workflow_package_has_standard_modules(graph_id):
    package = f"app.workflows.{graph_id}"
    assert importlib.import_module(f"{package}.state")
    assert importlib.import_module(f"{package}.edges")
    module = importlib.import_module(f"{package}.graph")
    assert callable(module.graph.invoke)
```

`test_workflow_state_contracts.py` 对 Product、Operations、Support 三个 state 执行同一 contract matrix：`graph_revision` 和 `state_schema_version >= 1` 必填；`json.dumps(state, default=pydantic_json_default)` 可序列化；Annotated reducer 对并行更新确定合并；每个 node 调用前后输入 state 深拷贝相等；字段值递归禁止 `SecretStr`、provider/SDK client、repository、checkpointer/store、`RequestContext`、`GraphRuntimeContext` 和任意带 `invoke/execute` 的宽泛运行对象。

```python
@pytest.mark.parametrize("case", build_workflow_state_contract_cases())
def test_state_is_versioned_serializable_and_runtime_free(case):
    state = case.make_state()
    assert state["graph_revision"] == case.graph_revision
    assert state["state_schema_version"] >= 1
    json.dumps(state, default=pydantic_json_default)
    assert find_forbidden_runtime_values(state) == []
```

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/contract/test_langgraph_contract.py -q`

Expected: FAIL，标准 package 尚不存在。

- [ ] **Step 3: 拆分 Product Launch**

`agents/graphs/state.py` 迁为 product state；routes 合并成 `edges.py`；nodes 拆为 research、profit、suppliers、localization、listing、risk、approval、publish、completion。`graph.py` 只 add_node/add_edge/compile。现有 preview/resume/trace/snapshot helpers 精确移到 `runtime/product_launch.py` 和 `observability/recorders.py`，本计划暂时保持 legacy 两图行为。所有 node 使用 `Mapping` 输入并只返回新建增量 dict，禁止原地写 state。

- [ ] **Step 4: 拆分 Operations**

`agents/graphs/operations/state.py`、`routes.py`、`workflow.py`、`nodes.py` 分别映射到标准 state/edges/graph/nodes；节点按 load、diagnose、propose、complete 拆分。Seeded read port 由 container/build-time dependency 注入，node 只返回增量且 contract test 证明输入未修改。

- [ ] **Step 5: 将 Node 19 service 包装为可工作的 Support baseline graph**

```python
class SupportState(TypedDict, total=False):
    graph_revision: str
    state_schema_version: int
    request: SupportRequest
    response: SupportResponse
    errors: list[str]


def build_support_graph(container: ApplicationContainer):
    builder = StateGraph(SupportState, context_schema=GraphRuntimeContext)
    builder.add_node("answer", make_answer_node(container.support_service))
    builder.add_edge(START, "answer")
    builder.add_edge("answer", END)
    return builder.compile(checkpointer=container.checkpointer, store=container.store)
```

这是 Node 19 现有 service 的标准 graph 适配，不是空占位；后续计划再拆成 planner/retrieve/tool/finalize 多节点图。

- [ ] **Step 6: 实现 GraphRegistry 与模块级单例**

```python
@dataclass(frozen=True, slots=True)
class GraphRegistry:
    product_launch: CompiledStateGraph
    operations: CompiledStateGraph
    support: CompiledStateGraph
```

默认模块级 graph 使用同一个缓存 container；测试通过 factory 构建隔离图。

- [ ] **Step 7: 运行聚焦、全量并提交**

Run: `python -m pytest tests/unit/workflows tests/integration/workflows -q`

Run: `python -m pytest -q`

```text
git diff --check
git commit -m "重构：按标准模块拆分三类 Agent 工作流"
```

---

### Task 6: LangGraph Manifest 契约

**Files:**
- Create: `backend/langgraph.json`
- Create: `backend/tests/contract/test_langgraph_manifest.py`

- [ ] **Step 1: 写入 manifest RED 测试**

```python
EXPECTED_GRAPHS = {
    "product_launch": "./src/app/workflows/product_launch/graph.py:graph",
    "operations": "./src/app/workflows/operations/graph.py:graph",
    "support": "./src/app/workflows/support/graph.py:graph",
}


def test_langgraph_manifest_exports_three_graphs():
    manifest = json.loads((BACKEND_ROOT / "langgraph.json").read_text("utf-8"))
    assert manifest["graphs"] == EXPECTED_GRAPHS
    for target in EXPECTED_GRAPHS.values():
        graph = load_export(target)
        assert callable(graph.invoke)
        assert callable(graph.stream)
        assert callable(graph.get_state)
```

- [ ] **Step 2: 运行 RED**

Run: `python -m pytest tests/contract/test_langgraph_manifest.py -q`

Expected: FAIL，manifest 不存在。

- [ ] **Step 3: 创建固定 manifest 并验证 app 复用同一实例**

使用设计规范中的三图 JSON。测试额外断言 `app.state.graphs` 中对象与模块 export 为同一实例。

- [ ] **Step 4: 运行 GREEN 并提交**

Run: `python -m pytest tests/contract/test_langgraph_manifest.py -q`

```text
git diff --check
git commit -m "构建：注册 LangGraph 三工作流清单"
```

---

### Task 7: 测试分层与 Eval 资源迁移

**Files:**
- Move: `backend/tests/test_profit.py` to `backend/tests/unit/services/test_profit.py`
- Move: `backend/tests/test_risk.py` to `backend/tests/unit/services/test_risk.py`
- Move: `backend/tests/test_suppliers.py` to `backend/tests/unit/services/test_suppliers.py`
- Move: `backend/tests/test_marketplace_adapters.py` to `backend/tests/unit/adapters/test_marketplace_adapters.py`
- Move: `backend/tests/test_config.py` to `backend/tests/unit/configuration/test_config.py`
- Move: `backend/tests/test_agent_boundaries.py` to `backend/tests/unit/tools/test_agent_boundaries.py`
- Move: `backend/tests/test_security_isolation.py` to `backend/tests/unit/tools/test_security_isolation.py`
- Move: `backend/tests/test_tool_executor.py` to `backend/tests/unit/tools/test_tool_executor.py`
- Move: `backend/tests/test_agent_engineering_contract.py` to `backend/tests/contract/test_agent_engineering_contract.py`
- Move: `backend/tests/test_langgraph_contract.py` to `backend/tests/contract/test_langgraph_contract.py`
- Move: `backend/tests/test_tool_registry.py` to `backend/tests/contract/test_tool_registry.py`
- Move: `backend/tests/test_approval_repository.py` to `backend/tests/integration/persistence/test_approval_repository.py`
- Move: `backend/tests/test_trace_events.py` to `backend/tests/integration/persistence/test_trace_events.py`
- Move: `backend/tests/test_workflow_snapshots.py` to `backend/tests/integration/persistence/test_workflow_snapshots.py`
- Move: `backend/tests/test_product_launch_graph.py` to `backend/tests/integration/workflows/test_product_launch_graph.py`
- Move: `backend/tests/test_operations_agent.py` to `backend/tests/integration/workflows/test_operations_agent.py`
- Move: `backend/tests/test_support_rag.py` to `backend/tests/integration/rag/test_support_rag.py`
- Move: `backend/tests/test_product_launch_golden.py` to `backend/tests/integration/evals/test_product_launch_golden.py`
- Move: `backend/src/app/agents/evaluation/results.py` to `backend/evals/product_launch/results.py`
- Move: `backend/src/app/agents/evaluation/runner.py` to `backend/evals/product_launch/runner.py`
- Move: `backend/src/app/agents/evaluation/registry.py` to `backend/evals/product_launch/registry.py`
- Move: `backend/src/app/rag/support/evaluation.py` to `backend/evals/evaluators/support.py`
- Create: `backend/evals/__init__.py`
- Create: `backend/evals/evaluators/__init__.py`
- Create: `backend/evals/product_launch/__init__.py`
- Create: `backend/evals/support/__init__.py`
- Create: `backend/evals/support/v1/cases.json`
- Modify: `backend/tests/conftest.py`

- [ ] **Step 1: 写入测试布局 RED 契约**

```python
def test_no_flat_test_modules_remain():
    flat = [
        path
        for path in (BACKEND_ROOT / "tests").iterdir()
        if path.is_file() and path.name.startswith("test_") and path.suffix == ".py"
    ]
    assert flat == []
```

- [ ] **Step 2: 按设计分类移动**

精确移动表：

| 来源 | 目标 |
|---|---|
| `tests/test_profit.py` | `tests/unit/services/test_profit.py` |
| `tests/test_risk.py` | `tests/unit/services/test_risk.py` |
| `tests/test_suppliers.py` | `tests/unit/services/test_suppliers.py` |
| `tests/test_marketplace_adapters.py` | `tests/unit/adapters/test_marketplace_adapters.py` |
| `tests/test_config.py` | `tests/unit/configuration/test_config.py` |
| `tests/test_agent_boundaries.py` | `tests/unit/tools/test_agent_boundaries.py` |
| `tests/test_security_isolation.py` | `tests/unit/tools/test_security_isolation.py` |
| `tests/test_tool_executor.py` | `tests/unit/tools/test_tool_executor.py` |
| `tests/test_agent_engineering_contract.py` | `tests/contract/test_agent_engineering_contract.py` |
| `tests/test_langgraph_contract.py` | `tests/contract/test_langgraph_contract.py` |
| `tests/test_tool_registry.py` | `tests/contract/test_tool_registry.py` |
| `tests/test_approval_repository.py` | `tests/integration/persistence/test_approval_repository.py` |
| `tests/test_trace_events.py` | `tests/integration/persistence/test_trace_events.py` |
| `tests/test_workflow_snapshots.py` | `tests/integration/persistence/test_workflow_snapshots.py` |
| `tests/test_product_launch_graph.py` | `tests/integration/workflows/test_product_launch_graph.py` |
| `tests/test_operations_agent.py` | `tests/integration/workflows/test_operations_agent.py` |
| `tests/test_support_rag.py` | `tests/integration/rag/test_support_rag.py` |
| `tests/test_product_launch_golden.py` | `tests/integration/evals/test_product_launch_golden.py` |

后续任务可以从大文件拆出更细 unit/contract tests，但不得删除原断言。`conftest.py` 提供 fresh container、graph registry、app、client、request/graph context 和 thread config factory。

- [ ] **Step 3: 迁移 eval 资源**

Node 16 的 results/runner/registry 进入上述 `evals/product_launch` 精确路径；既有十四个 Product JSON 保持原文件名。Node 19 evaluation 进入 `evals/evaluators/support.py`，其内嵌十类 case 机械搬入 `evals/support/v1/cases.json`。本任务只迁移既有行为，统一 canonical/CLI 留给最终质量计划。

- [ ] **Step 4: 分层与全量验证**

Run: `python -m pytest tests/unit -q`

Run: `python -m pytest tests/contract -q`

Run: `python -m pytest tests/integration -q`

Run: `python -m pytest tests/e2e -q`

Run: `python -m pytest -q`

Expected: 总测试数量与移动前一致或因新增 contract 测试增加，不得减少既有行为覆盖。

- [ ] **Step 5: 提交**

```text
git diff --check
git commit -m "测试：完成后端测试分层与评估资源迁移"
```

---

### Task 8: 工程入口、文档与旧路径退役

**Files:**
- Create: `backend/.env.example`
- Create: `backend/.gitignore`
- Create: `backend/README.md`
- Create: `backend/Dockerfile`
- Create: `backend/docker-compose.yml`
- Create: `.github/workflows/backend-ci.yml`
- Create: `backend/scripts/build_index.py`
- Create: `backend/migrations/README.md`
- Create: `backend/tests/contract/test_scripts_contract.py`
- Modify: `README.md`
- Modify: `.gitignore`
- Delete: `backend/requirements.txt`
- Delete: `backend/src/app/agents/`
- Delete: `backend/src/app/config/`
- Delete: `backend/src/app/repositories/`
- Delete: `backend/src/app/security/`
- Modify: `docs/progress/2026-07-14-langgraph-standard-runtime-integration.md`

- [ ] **Step 1: 将项目布局 xfail 转为普通断言**

Run: `python -m pytest tests/contract/test_project_layout.py -q`

Expected: RED，旧 requirements 或旧目录仍存在。

- [ ] **Step 2: 补齐运行入口**

README 使用 `python -m pip install -e ".[dev]"`、`uvicorn app.api.app:app`、pytest 和 manifest 检查。Docker 使用 Python 3.12 slim、安装 pyproject、非 root 用户、healthcheck。CI 本阶段先运行 install、compileall、pytest、manifest；最终 eval/secret 门禁由后续计划扩展。

`scripts/build_index.py` 提供 `main(argv=None) -> int`：从 `app.mock_data.support_kb` 加载版本化语料，使用 Node 19 词法索引执行幂等摄取，输出只含 source/chunk/count/version/hash 的质量报告；`--dry-run` 不写文件。`test_scripts_contract.py` 先 RED 验证 `--dry-run` exit 0、重复运行摘要一致、报告不含正文或 secret，再实现 GREEN。`migrations/README.md` 明确当前 memory profile 无 SQL migration，PostgreSQL profile 的 schema migration 必须在引入真实仓储时单独新增，不放空 SQL 占位。

- [ ] **Step 3: 退役旧依赖与路径**

删除 `requirements.txt` 和所有旧目录；搜索不得命中 `app.main`、`backend/app`、`app.agents`、`app.repositories`。

- [ ] **Step 4: 最终验证**

```text
python -m pip install -e ".[dev]"
python -m compileall -q src/app
python -m pytest -q
python -m pytest tests/contract/test_langgraph_manifest.py -q
docker build -t eshop-agent-backend .
docker run --rm eshop-agent-backend python -c "from app.api.app import app; assert app"
docker compose config
```

From repository root:

```text
rg -n "requirements\.txt|app\.main|backend/app|app\.agents|app\.repositories" backend/src backend/README.md backend/Dockerfile backend/docker-compose.yml .github/workflows README.md
git diff --check
```

Expected: 搜索除历史设计/计划说明外不命中生产代码或运行文档；所有命令通过。

- [ ] **Step 5: 提交并推送**

```text
git commit -m "构建：补齐后端标准工程入口并退役旧路径"
git push origin dev-com
```

在 progress log 写入唯一一行 `LAYOUT_FINAL_SHA=` 加当前 `git rev-parse HEAD` 的 40 位小写 SHA，并记录迁移前后全量测试数量、manifest/Docker 验证和 reviewer 结论。下一阶段按固定正则读取该行。
