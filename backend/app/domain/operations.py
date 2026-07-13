from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import Marketplace, RiskLevel


RecordType = Literal["order", "inventory", "shipment", "metric"]
OrderStatus = Literal["pending", "paid", "fulfilled", "cancelled", "returned", "refunded"]
ShipmentStatus = Literal["pending", "in_transit", "delivered", "delayed", "exception"]
MetricName = Literal["conversion_rate", "return_rate"]
FreshnessCode = Literal["duplicate_ignored", "future_excluded", "stale", "late_arrival", "out_of_order"]
AnomalyType = Literal["low_stock", "shipment_delay", "conversion_drop", "return_rate_rise"]
ActionType = Literal[
    "replenish_inventory",
    "review_support_strategy",
    "review_pricing",
    "optimize_listing",
]
FailureCode = Literal[
    "seed_validation_failed",
    "source_read_failed",
    "tenant_mismatch",
    "event_conflict",
    "listing_version_conflict",
]

ListingContentHash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class OperationsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)


class OperationsEvent(OperationsModel):
    event_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    marketplace: Marketplace
    listing_id: str = Field(min_length=1)
    listing_version_id: str = Field(min_length=1)
    listing_content_hash: ListingContentHash
    sku: str = Field(min_length=1)
    observed_at: AwareDatetime
    received_at: AwareDatetime


class OrderEvent(OperationsEvent):
    record_type: Literal["order"]
    order_id: str = Field(min_length=1)
    status: OrderStatus
    quantity: int = Field(ge=1)
    gross_revenue: Decimal = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class InventoryEvent(OperationsEvent):
    record_type: Literal["inventory"]
    available_quantity: int = Field(ge=0)
    reserved_quantity: int = Field(ge=0)
    reorder_point: int = Field(ge=0)


class ShipmentEvent(OperationsEvent):
    record_type: Literal["shipment"]
    shipment_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    status: ShipmentStatus
    promised_delivery_at: AwareDatetime
    estimated_delivery_at: AwareDatetime


class MetricEvent(OperationsEvent):
    record_type: Literal["metric"]
    metric_name: MetricName
    value: float = Field(ge=0)
    window_start: AwareDatetime
    window_end: AwareDatetime

    @model_validator(mode="after")
    def validate_window(self) -> MetricEvent:
        if self.window_end <= self.window_start:
            raise ValueError("metric window_end must be after window_start")
        return self


OperationsRecord = Annotated[
    OrderEvent | InventoryEvent | ShipmentEvent | MetricEvent,
    Field(discriminator="record_type"),
]


class OperationsReadQuery(OperationsModel):
    tenant_id: str = Field(min_length=1)
    as_of: AwareDatetime
    marketplaces: list[Marketplace] | None = None
    listing_version_ids: list[str] | None = None


class FreshnessPolicy(OperationsModel):
    order_max_age_seconds: int = Field(default=86_400, gt=0)
    inventory_max_age_seconds: int = Field(default=21_600, gt=0)
    shipment_max_age_seconds: int = Field(default=21_600, gt=0)
    metric_max_age_seconds: int = Field(default=172_800, gt=0)
    late_arrival_seconds: int = Field(default=43_200, gt=0)


class AnomalyThresholds(OperationsModel):
    shipment_delay_seconds: int = Field(default=86_400, ge=0)
    conversion_relative_drop: float = Field(default=0.20, ge=0, le=1)
    return_rate_absolute_rise: float = Field(default=0.03, ge=0, le=1)


class OperationsDiagnostic(OperationsModel):
    tenant_id: str = Field(min_length=1)
    code: FreshnessCode
    event_id: str = Field(min_length=1)
    record_type: RecordType
    listing_version_id: str = Field(min_length=1)
    observed_at: AwareDatetime
    received_at: AwareDatetime


class OpsFailure(OperationsModel):
    tenant_id: str = Field(min_length=1)
    code: FailureCode
    message: str = Field(min_length=1)
    source_event_ids: list[str] = Field(default_factory=list)
    listing_version_ids: list[str] = Field(default_factory=list)


class OperationsReadModel(OperationsModel):
    tenant_id: str = Field(min_length=1)
    as_of: AwareDatetime
    records: list[OperationsRecord] = Field(default_factory=list)
    fresh_records: list[OperationsRecord] = Field(default_factory=list)
    stale_records: list[OperationsRecord] = Field(default_factory=list)
    diagnostics: list[OperationsDiagnostic] = Field(default_factory=list)
    failure: OpsFailure | None = None


class OpsPerformanceSummary(OperationsModel):
    summary_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    marketplace: Marketplace
    listing_id: str = Field(min_length=1)
    listing_version_id: str = Field(min_length=1)
    listing_content_hash: ListingContentHash
    sku: str = Field(min_length=1)
    as_of: AwareDatetime
    source_event_ids: list[str] = Field(default_factory=list)
    order_count: int = Field(default=0, ge=0)
    units_sold: int = Field(default=0, ge=0)
    gross_revenue: Decimal = Field(default=Decimal("0"), ge=0)
    available_quantity: int | None = Field(default=None, ge=0)
    reserved_quantity: int | None = Field(default=None, ge=0)
    conversion_rate: float | None = Field(default=None, ge=0)
    return_rate: float | None = Field(default=None, ge=0)


class OpsEvidence(OperationsModel):
    evidence_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    anomaly_type: AnomalyType
    marketplace: Marketplace
    listing_id: str = Field(min_length=1)
    listing_version_id: str = Field(min_length=1)
    listing_content_hash: ListingContentHash
    sku: str = Field(min_length=1)
    source_event_ids: list[str] = Field(min_length=1)
    observed_at: AwareDatetime
    current_value: float
    baseline_value: float | None = None
    threshold_value: float
    summary: str = Field(min_length=1)


class OpsAnomaly(OperationsModel):
    anomaly_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    anomaly_type: AnomalyType
    marketplace: Marketplace
    listing_id: str = Field(min_length=1)
    listing_version_id: str = Field(min_length=1)
    listing_content_hash: ListingContentHash
    sku: str = Field(min_length=1)
    source_event_ids: list[str] = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    detected_at: AwareDatetime
    summary: str = Field(min_length=1)


class OpsActionProposal(OperationsModel):
    proposal_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    action_type: ActionType
    status: Literal["proposed"] = "proposed"
    execution_allowed: Literal[False] = False
    approval_required_for_execution: Literal[True] = True
    risk_level: Literal[RiskLevel.HIGH] = RiskLevel.HIGH
    anomaly_ids: list[str] = Field(min_length=1)
    source_event_ids: list[str] = Field(min_length=1)
    marketplace: Marketplace
    listing_id: str = Field(min_length=1)
    listing_version_id: str = Field(min_length=1)
    listing_content_hash: ListingContentHash
    sku: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


class OperationsReadError(RuntimeError):
    def __init__(
        self,
        *,
        code: FailureCode,
        tenant_id: str = "unknown",
        message: str,
        source_event_ids: list[str] | None = None,
        listing_version_ids: list[str] | None = None,
    ) -> None:
        self.failure = OpsFailure(
            tenant_id=tenant_id,
            code=code,
            message=message,
            source_event_ids=source_event_ids or [],
            listing_version_ids=listing_version_ids or [],
        )
        super().__init__(f"{self.failure.code}: {self.failure.message}")

    @property
    def code(self) -> FailureCode:
        return self.failure.code

    @property
    def tenant_id(self) -> str:
        return self.failure.tenant_id
