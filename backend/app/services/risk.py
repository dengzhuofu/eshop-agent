from pydantic import BaseModel

from app.domain.enums import RiskLevel
from app.domain.schemas import ValidationResult
from app.services.profit import ProfitEstimate


class RiskAssessment(BaseModel):
    risk_level: RiskLevel
    requires_approval: bool
    reasons: list[str]


def classify_listing_risk(
    validation: ValidationResult,
    profit: ProfitEstimate,
) -> RiskAssessment:
    reasons: list[str] = []
    levels: list[RiskLevel] = []

    for issue in validation.issues:
        reasons.append(f"Validation issue: {issue.field}")
        levels.append(issue.risk_level)

    if profit.contribution_margin_rate < 0.15:
        reasons.append("Contribution margin below 15%")
        levels.append(RiskLevel.HIGH)
    elif profit.contribution_margin_rate < 0.25:
        reasons.append("Contribution margin below 25%")
        levels.append(RiskLevel.MEDIUM)

    if RiskLevel.CRITICAL in levels:
        risk_level = RiskLevel.CRITICAL
    elif RiskLevel.HIGH in levels:
        risk_level = RiskLevel.HIGH
    elif RiskLevel.MEDIUM in levels:
        risk_level = RiskLevel.MEDIUM
    else:
        risk_level = RiskLevel.LOW

    return RiskAssessment(
        risk_level=risk_level,
        requires_approval=risk_level in {RiskLevel.HIGH, RiskLevel.CRITICAL},
        reasons=reasons,
    )
