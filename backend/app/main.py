from fastapi import FastAPI

from app.api.routes.agents import router as agents_router
from app.api.routes.approvals import router as approvals_router
from app.api.routes.health import router as health_router
from app.api.routes.marketplaces import router as marketplaces_router
from app.api.routes.workflows import router as workflows_router


def create_app() -> FastAPI:
    app = FastAPI(title="Eshop Agent API", version="0.1.0")
    app.include_router(agents_router)
    app.include_router(approvals_router)
    app.include_router(health_router)
    app.include_router(marketplaces_router)
    app.include_router(workflows_router)
    return app


app = create_app()
