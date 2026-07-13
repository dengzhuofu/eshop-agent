import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import Marketplace, RiskLevel, WorkflowState

NonEmptyString = Annotated[str, Field(min_length=1)]
Sha256Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonNegativeInt = Annotated[int, Field(ge=0)]


class StrictEvaluationModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListingValidationEvaluationSummary(StrictEvaluationModel):
    marketplace: Marketplace
    listing_version_id: NonEmptyString
    valid: bool
    issue_codes: list[str]


class SelectedListingVersionEvaluationSummary(StrictEvaluationModel):
    marketplace: Marketplace
    version_id: NonEmptyString
    content_hash: Sha256Hash
    stage: NonEmptyString


class PublishEvaluationSummary(StrictEvaluationModel):
    marketplace: Marketplace
    listing_version_id: NonEmptyString
    status: Literal["published", "failed"]
    external_listing_id: str | None = None
    error_type: str | None = None


class ProductLaunchEvaluationSummary(StrictEvaluationModel):
    tenant_id: NonEmptyString
    workflow_id: NonEmptyString
    final_state: WorkflowState
    risk_level: RiskLevel
    profit_risk_level: RiskLevel
    supplier_risk_level: RiskLevel
    selected_supplier_id: str | None
    localization_risk_count: NonNegativeInt
    approval_request_id: str | None
    approval_status: str | None
    approval_reasons: list[str]
    snapshot_id: str | None
    snapshot_version: int | None = Field(default=None, ge=1)
    validation: list[ListingValidationEvaluationSummary]
    selected_listing_versions: list[SelectedListingVersionEvaluationSummary]
    publish: list[PublishEvaluationSummary]
    errors: list[str]
    trace_counts: dict[str, NonNegativeInt]
    publish_trace_statuses: list[Literal["published", "failed"]]


class EvaluationMetric(StrictEvaluationModel):
    name: NonEmptyString
    score: float = Field(ge=0, le=1)
    threshold: float = Field(default=1.0, ge=0, le=1)
    passed: bool
    reason: NonEmptyString


class EvaluationResult(StrictEvaluationModel):
    schema_version: Literal["evaluation-result/v1"]
    evaluation_id: NonEmptyString
    scenario_id: NonEmptyString
    scenario_version: int = Field(ge=1)
    tenant_id: NonEmptyString
    workflow_id: NonEmptyString
    status: Literal["passed", "failed"]
    score: float = Field(ge=0, le=1)
    threshold: float = Field(default=1.0, ge=0, le=1)
    metrics: list[EvaluationMetric]
    expected_summary_hash: Sha256Hash
    actual_summary_hash: Sha256Hash
    actual_summary: ProductLaunchEvaluationSummary
    failure_reasons: list[str]


def canonical_summary_hash(summary: ProductLaunchEvaluationSummary) -> str:
    canonical_json = json.dumps(
        summary.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
