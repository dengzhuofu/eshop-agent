import hashlib

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.graphs.workflows.product_launch import (
    run_product_launch_preview,
    run_product_launch_publish_resume,
)
from app.domain.enums import Marketplace, WorkflowState
from app.repositories.approvals import get_approval_repository
from app.repositories.events import TraceEventConflictError, get_trace_event_repository
from app.repositories.snapshots import get_workflow_snapshot_repository

router = APIRouter(prefix="/workflows", tags=["workflows"])


class WorkflowCreateRequest(BaseModel):
    product_idea: str = Field(min_length=1)
    target_marketplaces: list[Marketplace]
    target_price: float = Field(gt=0)
    risk_preference: str = "balanced"


class WorkflowResumeRequest(BaseModel):
    approval_request_id: str = Field(min_length=1)


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
    snapshot = get_workflow_snapshot_repository().get_latest(workflow_id, tenant_id="demo-tenant")

    return {
        "workflow_id": workflow_id,
        "state": WorkflowState(state["current_step"]).value,
        "product_idea": request.product_idea,
        "target_marketplaces": [marketplace.value for marketplace in request.target_marketplaces],
        "profit_estimate": state["profit_estimate"],
        "supplier_evaluations": state["supplier_evaluations"],
        "selected_supplier_id": state["selected_supplier_id"],
        "supplier_risk_level": state["supplier_risk_level"],
        "listing_validations": state["listing_validations"],
        "approval_required": state["approval_required"],
        "approval_request_id": state["approval_request_id"],
        "approval_request": state["approval_request"],
        "approval_reasons": state["approval_reasons"],
        "snapshot": None
        if snapshot is None
        else {
            "id": snapshot.id,
            "checkpoint_name": snapshot.checkpoint_name,
            "version": snapshot.version,
        },
        "completed_steps": state["completed_steps"],
    }


@router.post("/{workflow_id}/resume")
def resume_workflow(workflow_id: str, request: WorkflowResumeRequest) -> dict:
    approval = get_approval_repository().get(request.approval_request_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval request not found")

    if approval.workflow_id != workflow_id:
        raise HTTPException(status_code=409, detail="Approval request does not match workflow")

    state = run_product_launch_publish_resume(request.approval_request_id)
    if WorkflowState(state["current_step"]) == WorkflowState.FAILED:
        raise HTTPException(status_code=409, detail=state["errors"])

    return {
        "workflow_id": workflow_id,
        "state": WorkflowState(state["current_step"]).value,
        "approval_request_id": state["approval_request_id"],
        "publish_results": state["publish_results"],
        "tool_calls": state["tool_calls"],
        "completed_steps": state["completed_steps"],
    }


@router.get("/{workflow_id}/events")
def list_workflow_events(workflow_id: str) -> dict:
    try:
        events = get_trace_event_repository().list_by_workflow(workflow_id, tenant_id="demo-tenant")
    except TraceEventConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return {
        "workflow_id": workflow_id,
        "events": [event.model_dump(mode="json") for event in events],
    }
