from datetime import UTC, datetime
from threading import RLock
from typing import Any

from app.domain.approvals import ApprovalRequest
from app.domain.enums import ApprovalStatus, RiskLevel


class ApprovalConflictError(ValueError):
    pass


class ApprovalRepository:
    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}
        self._lock = RLock()

    def upsert_pending(
        self,
        approval_id: str,
        workflow_id: str,
        tenant_id: str,
        requested_by: str,
        reason_codes: list[str],
        risk_level: RiskLevel,
        resource_type: str,
        resource_id: str,
        metadata: dict[str, Any],
    ) -> ApprovalRequest:
        with self._lock:
            existing = self._requests.get(approval_id)
            if existing is not None:
                return existing.model_copy(deep=True)

            request = ApprovalRequest(
                id=approval_id,
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                requested_by=requested_by,
                reason_codes=reason_codes,
                risk_level=risk_level,
                resource_type=resource_type,
                resource_id=resource_id,
                metadata=metadata,
                created_at=datetime.now(UTC),
            )
            self._requests[approval_id] = request
            return request.model_copy(deep=True)

    def list(self) -> list[ApprovalRequest]:
        with self._lock:
            return [request.model_copy(deep=True) for request in self._requests.values()]

    def get(self, approval_id: str | None) -> ApprovalRequest | None:
        if approval_id is None:
            return None
        with self._lock:
            request = self._requests.get(approval_id)
            if request is None:
                return None
            return request.model_copy(deep=True)

    def approve(self, approval_id: str, reviewer_id: str, comment: str | None = None) -> ApprovalRequest:
        return self._transition(
            approval_id=approval_id,
            target_status=ApprovalStatus.APPROVED,
            reviewer_id=reviewer_id,
            comment=comment,
        )

    def reject(self, approval_id: str, reviewer_id: str, comment: str | None = None) -> ApprovalRequest:
        return self._transition(
            approval_id=approval_id,
            target_status=ApprovalStatus.REJECTED,
            reviewer_id=reviewer_id,
            comment=comment,
        )

    def clear(self) -> None:
        with self._lock:
            self._requests.clear()

    def replace(self, request: ApprovalRequest) -> ApprovalRequest:
        with self._lock:
            stored = request.model_copy(deep=True)
            self._requests[request.id] = stored
            return stored.model_copy(deep=True)

    def _transition(
        self,
        approval_id: str,
        target_status: ApprovalStatus,
        reviewer_id: str,
        comment: str | None,
    ) -> ApprovalRequest:
        with self._lock:
            request = self._requests.get(approval_id)
            if request is None:
                raise KeyError(approval_id)

            if request.status == target_status:
                return request.model_copy(deep=True)

            if request.status == ApprovalStatus.APPROVED:
                raise ApprovalConflictError("Approval request is already approved")
            if request.status == ApprovalStatus.REJECTED:
                raise ApprovalConflictError("Approval request is already rejected")

            updated = request.model_copy(
                update={
                    "status": target_status,
                    "reviewed_at": datetime.now(UTC),
                    "reviewed_by": reviewer_id,
                    "review_comment": comment,
                },
                deep=True,
            )
            self._requests[approval_id] = updated
            return updated.model_copy(deep=True)


_approval_repository = ApprovalRepository()


def get_approval_repository() -> ApprovalRepository:
    return _approval_repository
