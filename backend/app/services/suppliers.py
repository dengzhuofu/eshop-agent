from pydantic import BaseModel, Field


class SupplierInput(BaseModel):
    supplier_id: str = Field(min_length=1)
    unit_price: float = Field(gt=0)
    moq: int = Field(gt=0)
    lead_time_days: int = Field(gt=0)
    quality_score: float = Field(ge=0, le=1)
    defect_rate: float = Field(ge=0, le=1)
    response_time_hours: int = Field(gt=0)
    has_required_certifications: bool


class SupplierScore(BaseModel):
    supplier_id: str
    total_score: int
    risk_level: str
    recommended: bool
    risk_notes: list[str]


def score_supplier(data: SupplierInput) -> SupplierScore:
    quality_points = round(data.quality_score * 35)
    price_points = max(0, min(20, round(20 - max(data.unit_price - 8, 0) * 2)))
    moq_points = 10 if data.moq <= 500 else 5 if data.moq <= 1000 else 0
    lead_time_points = 15 if data.lead_time_days <= 14 else 8 if data.lead_time_days <= 30 else 0
    defect_points = 10 if data.defect_rate <= 0.03 else 5 if data.defect_rate <= 0.08 else 0
    response_points = 8 if data.response_time_hours <= 12 else 4 if data.response_time_hours <= 36 else 0
    certification_points = 5 if data.has_required_certifications else 0

    total_score = (
        quality_points
        + price_points
        + moq_points
        + lead_time_points
        + defect_points
        + response_points
        + certification_points
    )

    risk_notes: list[str] = []
    if data.defect_rate > 0.08:
        risk_notes.append("High historical defect rate")
    if data.lead_time_days > 30:
        risk_notes.append("Long lead time")
    if data.moq > 1000:
        risk_notes.append("High MOQ")
    if not data.has_required_certifications:
        risk_notes.append("Missing required certifications")
    if data.quality_score < 0.75:
        risk_notes.append("Low quality score")

    if total_score >= 80 and not risk_notes:
        risk_level = "low"
    elif total_score >= 60:
        risk_level = "medium"
    else:
        risk_level = "high"

    return SupplierScore(
        supplier_id=data.supplier_id,
        total_score=total_score,
        risk_level=risk_level,
        recommended=risk_level == "low",
        risk_notes=risk_notes,
    )

