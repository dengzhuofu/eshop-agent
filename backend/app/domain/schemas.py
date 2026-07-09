from pydantic import BaseModel, Field

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

