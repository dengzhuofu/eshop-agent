from app.services.profit import ProfitInput, estimate_profit


def test_estimate_profit_calculates_landed_cost_and_margin():
    estimate = estimate_profit(
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

    assert estimate.landed_cost == 12.8
    assert estimate.break_even_price == 23.12
    assert estimate.contribution_margin == 5.29
    assert estimate.contribution_margin_rate == 0.18


def test_low_margin_profit_estimate_is_flagged():
    estimate = estimate_profit(
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

    assert estimate.contribution_margin < 0
    assert estimate.profit_risk == "high"
