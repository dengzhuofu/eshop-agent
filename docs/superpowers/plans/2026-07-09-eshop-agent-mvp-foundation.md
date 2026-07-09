# Eshop Agent MVP Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first production-minded foundation for the cross-border e-commerce Agent platform: repository setup, backend domain core, model configuration, mock marketplace adapters, tool registry, and a minimal API that can be tested locally.

**Architecture:** Start with a Python FastAPI backend because the PRD prioritizes Agent workflow, tools, RAG, and deterministic business services. Keep LLM calls behind a provider interface and keep all business actions behind typed tools and adapters. Frontend work will start after the workflow API shape is stable.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, pytest, httpx, python-dotenv, optional SiliconFlow-compatible API client, future LangGraph orchestration, future PostgreSQL/Redis/Qdrant integrations.

## Global Constraints

- API key must only be read from environment variables such as `SILICONFLOW_API_KEY`; never commit real secrets.
- Default LLM provider is `siliconflow`.
- Default LLM base URL is `https://api.siliconflow.cn/v1`.
- Default LLM model is `deepseek-ai/DeepSeek-V3.2`.
- Default embedding model is `BAAI/bge-m3` with 1024 dimensions.
- Default reranker model is `BAAI/bge-reranker-v2-m3`.
- MVP uses mock marketplace adapters before real Amazon, Shopify, or TikTok Shop connectors.
- High-risk actions such as publish listing, update price, issue refund, and delist product require human approval.
- Deterministic calculations and marketplace validation must not depend on LLM output.
- Tests must not require a real API key or external services.

---

## File Structure

- `backend/app/main.py`: FastAPI app factory and route registration.
- `backend/app/config/settings.py`: Pydantic settings loaded from environment variables.
- `backend/app/config/models.py`: centralized model and retrieval defaults.
- `backend/app/domain/enums.py`: shared enums for marketplace, risk, workflow, and approval state.
- `backend/app/domain/schemas.py`: Pydantic schemas used by services, adapters, and API.
- `backend/app/adapters/base.py`: marketplace adapter protocol and base result types.
- `backend/app/adapters/mock_marketplaces.py`: MockAmazonAdapter, MockShopifyAdapter, MockTikTokShopAdapter.
- `backend/app/services/profit.py`: deterministic landed-cost and margin calculation.
- `backend/app/services/suppliers.py`: deterministic supplier scoring.
- `backend/app/services/risk.py`: risk classification and approval requirement rules.
- `backend/app/tools/registry.py`: typed tool registry with risk metadata.
- `backend/app/api/routes/health.py`: health endpoint.
- `backend/app/api/routes/marketplaces.py`: marketplace rule and validation endpoints.
- `backend/app/api/routes/workflows.py`: minimal workflow launch endpoint backed by deterministic services.
- `backend/tests/`: pytest coverage for config, adapters, tools, profit, suppliers, risk, and API.
- `backend/requirements.txt`: backend dependencies.
- `.env.example`: safe environment variable template.
- `.gitignore`: Python, Node, env, cache, and local output ignores.
- `README.md`: project overview, architecture, local setup, and roadmap.

## Task 1: Repository and Backend Skeleton

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/routes/__init__.py`
- Create: `backend/app/api/routes/health.py`
- Create: `backend/tests/test_health.py`

**Interfaces:**
- Produces: `create_app() -> FastAPI` in `backend/app/main.py`.
- Produces: `GET /health` returning `{"status": "ok", "service": "eshop-agent-api"}`.

- [ ] **Step 1: Write the failing health API test**

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_returns_service_status():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "eshop-agent-api"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_health.py -v`

Expected: FAIL because `app.main` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/main.py`:

```python
from fastapi import FastAPI

from app.api.routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Eshop Agent API", version="0.1.0")
    app.include_router(health_router)
    return app


app = create_app()
```

Create `backend/app/api/routes/health.py`:

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "eshop-agent-api"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_health.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .gitignore .env.example README.md backend
git commit -m "chore: initialize backend skeleton"
```

## Task 2: Centralized SiliconFlow-Compatible Configuration

**Files:**
- Create: `backend/app/config/__init__.py`
- Create: `backend/app/config/models.py`
- Create: `backend/app/config/settings.py`
- Create: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `MODEL_CONFIG: dict[str, dict[str, object]]`.
- Produces: `Settings` with `SILICONFLOW_API_KEY`, `SILICONFLOW_BASE_URL`, `LLM_MODEL`, `EMBEDDING_MODEL`, `RERANKER_MODEL`, `VISION_MODEL`.
- Produces: `get_settings() -> Settings`.

- [ ] **Step 1: Write failing config tests**

```python
from app.config.models import MODEL_CONFIG
from app.config.settings import Settings


def test_model_config_uses_siliconflow_defaults():
    assert MODEL_CONFIG["llm"]["provider"] == "siliconflow"
    assert MODEL_CONFIG["llm"]["model"] == "deepseek-ai/DeepSeek-V3.2"
    assert MODEL_CONFIG["embedding"]["model"] == "BAAI/bge-m3"
    assert MODEL_CONFIG["embedding"]["dimensions"] == 1024
    assert MODEL_CONFIG["reranker"]["model"] == "BAAI/bge-reranker-v2-m3"


def test_settings_do_not_require_real_api_key_for_tests(monkeypatch):
    monkeypatch.delenv("SILICONFLOW_API_KEY", raising=False)

    settings = Settings()

    assert settings.SILICONFLOW_API_KEY == ""
    assert settings.SILICONFLOW_BASE_URL == "https://api.siliconflow.cn/v1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_config.py -v`

Expected: FAIL because config modules do not exist yet.

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/config/models.py`:

```python
MODEL_CONFIG = {
    "llm": {
        "provider": "siliconflow",
        "model": "deepseek-ai/DeepSeek-V3.2",
        "base_url": "https://api.siliconflow.cn/v1",
        "temperature": 0.7,
        "max_tokens": 4096,
    },
    "embedding": {
        "provider": "siliconflow",
        "model": "BAAI/bge-m3",
        "dimensions": 1024,
    },
    "reranker": {
        "provider": "siliconflow",
        "model": "BAAI/bge-reranker-v2-m3",
        "top_n": 5,
    },
    "vision": {
        "provider": "siliconflow",
        "model": "Qwen/Qwen3-VL-32B-Instruct",
    },
}

RETRIEVAL_CONFIG = {
    "initial_top_k": 20,
    "rerank_top_k": 5,
    "score_threshold": 0.3,
    "max_refinements": 3,
}
```

Create `backend/app/config/settings.py`:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "Eshop Agent API"
    DEBUG: bool = False
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"
    LLM_MODEL: str = "deepseek-ai/DeepSeek-V3.2"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    VISION_MODEL: str = "Qwen/Qwen3-VL-32B-Instruct"


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_config.py tests/test_health.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/config backend/tests/test_config.py .env.example README.md
git commit -m "feat: add siliconflow model configuration"
```

## Task 3: Domain Schemas and Risk-Aware Marketplace Adapters

**Files:**
- Create: `backend/app/domain/__init__.py`
- Create: `backend/app/domain/enums.py`
- Create: `backend/app/domain/schemas.py`
- Create: `backend/app/adapters/__init__.py`
- Create: `backend/app/adapters/base.py`
- Create: `backend/app/adapters/mock_marketplaces.py`
- Create: `backend/tests/test_marketplace_adapters.py`

**Interfaces:**
- Produces: `Marketplace` enum values `amazon`, `shopify`, `tiktok_shop`.
- Produces: `ListingDraft`, `ValidationIssue`, `ValidationResult`, `PublishResult`.
- Produces: `MarketplaceAdapter` protocol.
- Produces: `get_mock_adapter(marketplace: Marketplace) -> MarketplaceAdapter`.

- [ ] **Step 1: Write failing adapter tests**

```python
from app.adapters.mock_marketplaces import get_mock_adapter
from app.domain.enums import Marketplace
from app.domain.schemas import ListingDraft


def test_amazon_adapter_rejects_missing_bullet_points():
    adapter = get_mock_adapter(Marketplace.AMAZON)
    draft = ListingDraft(
        marketplace=Marketplace.AMAZON,
        sku="SKU-1",
        title="Foldable under-bed storage organizer",
        description="Space-saving organizer.",
        bullet_points=[],
        price=29.99,
        attributes={"category": "home_storage"},
    )

    result = adapter.validate_listing(draft)

    assert result.valid is False
    assert any(issue.field == "bullet_points" for issue in result.issues)


def test_shopify_adapter_accepts_flexible_listing():
    adapter = get_mock_adapter(Marketplace.SHOPIFY)
    draft = ListingDraft(
        marketplace=Marketplace.SHOPIFY,
        sku="SKU-2",
        title="Foldable under-bed storage organizer",
        description="Space-saving organizer.",
        bullet_points=[],
        price=29.99,
        attributes={"category": "home_storage", "seo_title": "Under-bed organizer"},
    )

    result = adapter.validate_listing(draft)

    assert result.valid is True
    assert result.issues == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_marketplace_adapters.py -v`

Expected: FAIL because adapter modules do not exist.

- [ ] **Step 3: Write implementation**

Implement enum, schemas, base protocol, and three mock adapters with deterministic validation rules.

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_marketplace_adapters.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain backend/app/adapters backend/tests/test_marketplace_adapters.py
git commit -m "feat: add mock marketplace adapters"
```

## Task 4: Deterministic Profit, Supplier, and Risk Services

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/profit.py`
- Create: `backend/app/services/suppliers.py`
- Create: `backend/app/services/risk.py`
- Create: `backend/tests/test_profit.py`
- Create: `backend/tests/test_suppliers.py`
- Create: `backend/tests/test_risk.py`

**Interfaces:**
- Produces: `estimate_profit(input: ProfitInput) -> ProfitEstimate`.
- Produces: `score_supplier(input: SupplierInput) -> SupplierScore`.
- Produces: `classify_listing_risk(validation: ValidationResult, profit: ProfitEstimate) -> RiskAssessment`.

- [ ] **Step 1: Write failing deterministic service tests**

```python
from app.services.profit import ProfitInput, estimate_profit


def test_estimate_profit_calculates_break_even_price():
    estimate = estimate_profit(
        ProfitInput(
            unit_cost=8.0,
            shipping_cost=4.0,
            duty_rate=0.1,
            marketplace_fee_rate=0.15,
            payment_fee_rate=0.03,
            fulfillment_fee=3.0,
            ad_cost_per_unit=2.0,
            return_rate=0.05,
            target_price=29.99,
        )
    )

    assert estimate.landed_cost == 12.8
    assert estimate.break_even_price > 0
    assert estimate.contribution_margin > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_profit.py -v`

Expected: FAIL because service does not exist.

- [ ] **Step 3: Write implementation**

Implement deterministic formulas using Decimal or rounded float output to avoid LLM math.

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_profit.py tests/test_suppliers.py tests/test_risk.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services backend/tests/test_profit.py backend/tests/test_suppliers.py backend/tests/test_risk.py
git commit -m "feat: add deterministic business services"
```

## Task 5: Tool Registry and Minimal Workflow API

**Files:**
- Create: `backend/app/tools/__init__.py`
- Create: `backend/app/tools/registry.py`
- Create: `backend/app/api/routes/marketplaces.py`
- Create: `backend/app/api/routes/workflows.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_tool_registry.py`
- Create: `backend/tests/test_workflows_api.py`

**Interfaces:**
- Produces: `ToolDefinition`.
- Produces: `build_default_registry() -> ToolRegistry`.
- Produces: `POST /workflows` returning a deterministic MVP workflow preview.
- Produces: `GET /marketplaces/{marketplace}/rules`.

- [ ] **Step 1: Write failing tool registry test**

```python
from app.domain.enums import RiskLevel
from app.tools.registry import build_default_registry


def test_publish_listing_tool_requires_approval():
    registry = build_default_registry()

    tool = registry.get("publish_listing")

    assert tool.risk_level == RiskLevel.HIGH
    assert tool.requires_approval is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_tool_registry.py -v`

Expected: FAIL because registry module does not exist.

- [ ] **Step 3: Write implementation**

Implement registry and minimal API routes.

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_tool_registry.py tests/test_workflows_api.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/tools backend/app/api/routes backend/app/main.py backend/tests/test_tool_registry.py backend/tests/test_workflows_api.py
git commit -m "feat: add tool registry and workflow preview api"
```

## Task 6: Verification, Documentation, and Push

**Files:**
- Modify: `README.md`
- Modify: `.env.example`

**Interfaces:**
- Produces: local setup instructions.
- Produces: successful `pytest` run.
- Produces: Git remote `origin` pointing to `https://github.com/dengzhuofu/eshop-agent.git`.

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && pytest -v`

Expected: all tests PASS.

- [ ] **Step 2: Verify Git state**

Run: `git status --short`

Expected: no uncommitted implementation files after final commit.

- [ ] **Step 3: Verify remote**

Run: `git remote -v`

Expected: origin points to `https://github.com/dengzhuofu/eshop-agent.git`.

- [ ] **Step 4: Push**

Run: `git push -u origin main`

Expected: push succeeds, or fails with an authentication/permission message that does not affect local commit integrity.

## Self-Review Notes

- This first plan does not implement the full PRD. It implements the foundation needed for later Agent orchestration, approval center, RAG ingestion, frontend dashboard, async queue, persistence, and replay.
- No task requires real SiliconFlow API calls.
- Customer support RAG is documented in the PRD but deferred to a later implementation plan after core workflow and tool boundaries exist.
- Frontend is deferred until the backend API stabilizes.
