from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.domain.enums import ApprovalStatus, RiskLevel


class ApprovalRequest(BaseModel):
    id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    requested_by: str = Field(min_length=1)
    reason_codes: list[str] = Field(default_factory=list)
    risk_level: RiskLevel
    resource_type: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    status: ApprovalStatus = ApprovalStatus.PENDING
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None
    review_comment: str | None = None


class ApprovalActionRequest(BaseModel):
    reviewer_id: str = Field(min_length=1)
    comment: str | None = None
