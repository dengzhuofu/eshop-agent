from app.services.suppliers import SupplierInput, score_supplier


def test_supplier_score_rewards_price_quality_and_reliability():
    score = score_supplier(
        SupplierInput(
            supplier_id="SUP-1",
            unit_price=8.0,
            moq=300,
            lead_time_days=14,
            quality_score=0.92,
            defect_rate=0.02,
            response_time_hours=8,
            has_required_certifications=True,
        )
    )

    assert score.total_score >= 85
    assert score.risk_level == "low"
    assert score.recommended is True


def test_supplier_score_flags_high_defect_supplier():
    score = score_supplier(
        SupplierInput(
            supplier_id="SUP-2",
            unit_price=7.5,
            moq=1200,
            lead_time_days=45,
            quality_score=0.68,
            defect_rate=0.12,
            response_time_hours=48,
            has_required_certifications=False,
        )
    )

    assert score.total_score < 60
    assert score.risk_level == "high"
    assert score.recommended is False
    assert "Missing required certifications" in score.risk_notes
