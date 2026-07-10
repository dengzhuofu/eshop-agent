from fastapi import APIRouter, HTTPException

from app.domain.approvals import ApprovalActionRequest
from app.repositories.approvals import ApprovalConflictError, get_approval_repository

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("")
def list_approvals() -> dict:
    approvals = get_approval_repository().list()
    return {"approvals": [approval.model_dump(mode="json") for approval in approvals]}


@router.get("/{approval_id}")
def get_approval(approval_id: str) -> dict:
    approval = get_approval_repository().get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return approval.model_dump(mode="json")


@router.post("/{approval_id}/approve")
def approve_request(approval_id: str, request: ApprovalActionRequest) -> dict:
    try:
        approval = get_approval_repository().approve(
            approval_id,
            reviewer_id=request.reviewer_id,
            comment=request.comment,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Approval request not found") from exc
    except ApprovalConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return approval.model_dump(mode="json")


@router.post("/{approval_id}/reject")
def reject_request(approval_id: str, request: ApprovalActionRequest) -> dict:
    try:
        approval = get_approval_repository().reject(
            approval_id,
            reviewer_id=request.reviewer_id,
            comment=request.comment,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Approval request not found") from exc
    except ApprovalConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return approval.model_dump(mode="json")
