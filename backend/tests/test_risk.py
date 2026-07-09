from app.domain.enums import RiskLevel
from app.domain.schemas import ValidationIssue, ValidationResult
from app.services.profit import ProfitInput, estimate_profit
from app.services.risk import classify_listing_risk


def test_listing_risk_requires_approval_for_high_validation_issue():
    profit = estimate_profit(
        ProfitInput(
            unit_cost=8.0,
            shipping_cost=4.0,
            duty_rate=0.1,
            marketplace_fee_rate=0.15,
            payment_fee_rate=0.03,
            fulfillment_fee=3.0,
            ad_cost_per_unit=2.0,
            return_rate=0.05,
            target_price=29.99,
        )
    )
    validation = ValidationResult(
        valid=False,
        issues=[
            ValidationIssue(
                field="claims",
                message="Unsupported claim.",
                risk_level=RiskLevel.HIGH,
            )
        ],
    )

    assessment = classify_listing_risk(validation=validation, profit=profit)

    assert assessment.risk_level == RiskLevel.HIGH
    assert assessment.requires_approval is True
    assert "Validation issue: claims" in assessment.reasons


def test_listing_risk_requires_approval_for_low_profit():
    profit = estimate_profit(
        ProfitInput(
            unit_cost=15.0,
            shipping_cost=6.0,
            duty_rate=0.1,
            marketplace_fee_rate=0.15,
            payment_fee_rate=0.03,
            fulfillment_fee=4.0,
            ad_cost_per_unit=4.0,
            return_rate=0.1,
            target_price=29.99,
        )
    )
    validation = ValidationResult(valid=True, issues=[])

    assessment = classify_listing_risk(validation=validation, profit=profit)

    assert assessment.risk_level == RiskLevel.HIGH
    assert assessment.requires_approval is True
    assert "Contribution margin below 15%" in assessment.reasons
