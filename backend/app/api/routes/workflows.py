import hashlib

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agents.graphs.workflows.product_launch import run_product_launch_preview
from app.domain.enums import Marketplace, WorkflowState

router = APIRouter(prefix="/workflows", tags=["workflows"])


class WorkflowCreateRequest(BaseModel):
    product_idea: str = Field(min_length=1)
    target_marketplaces: list[Marketplace]
    target_price: float = Field(gt=0)
    risk_preference: str = "balanced"


def _workflow_id(request: WorkflowCreateRequest) -> str:
    raw = (
        f"{request.product_idea}:"
        f"{','.join(m.value for m in request.target_marketplaces)}:"
        f"{request.target_price}:"
        f"{request.risk_preference}"
    )
    return f"wf_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"


@router.post("")
def create_workflow(request: WorkflowCreateRequest) -> dict:
    workflow_id = _workflow_id(request)
    state = run_product_launch_preview(
        workflow_id=workflow_id,
        tenant_id="demo-tenant",
        product_idea=request.product_idea,
        target_marketplaces=request.target_marketplaces,
        target_price=request.target_price,
        risk_preference=request.risk_preference,
    )

    return {
        "workflow_id": workflow_id,
        "state": WorkflowState(state["current_step"]).value,
        "product_idea": request.product_idea,
        "target_marketplaces": [marketplace.value for marketplace in request.target_marketplaces],
        "profit_estimate": state["profit_estimate"],
        "listing_validations": state["listing_validations"],
        "approval_required": state["approval_required"],
        "approval_reasons": state["approval_reasons"],
        "completed_steps": state["completed_steps"],
    }
