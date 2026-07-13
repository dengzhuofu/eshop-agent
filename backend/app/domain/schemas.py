from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import Marketplace, RiskLevel


class ListingDraft(BaseModel):
    marketplace: Marketplace
    sku: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    bullet_points: list[str] = Field(default_factory=list)
    price: float = Field(gt=0)
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)
    locale: str = "en-US"


class ListingVersion(BaseModel):
    version_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    marketplace: Marketplace
    sku: str = Field(min_length=1)
    locale: str = Field(min_length=1)
    source_version_id: str | None = None
    version_number: int = Field(ge=1)
    stage: str = Field(min_length=1)
    draft: ListingDraft
    changes: list[str] = Field(default_factory=list)
    risk_flags: list[dict[str, Any]] = Field(default_factory=list)
    validation: dict[str, Any] | None = None
    created_by_agent: str = Field(min_length=1)
    created_step: str = Field(min_length=1)
    content_hash: str = Field(min_length=1)


class ListingApprovalIndex(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    listing_version_ids: list[str] = Field(min_length=1)
    listing_version_hashes: dict[str, str]


class ValidationIssue(BaseModel):
    field: str
    message: str
    risk_level: RiskLevel = RiskLevel.MEDIUM


class ValidationResult(BaseModel):
    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)


class PublishResult(BaseModel):
    listing_id: str
    status: str
    marketplace: Marketplace
    idempotency_key: str
