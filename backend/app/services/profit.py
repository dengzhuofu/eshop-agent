from pydantic import BaseModel, Field


class ProfitInput(BaseModel):
    unit_cost: float = Field(ge=0)
    shipping_cost: float = Field(ge=0)
    duty_rate: float = Field(ge=0, le=1)
    marketplace_fee_rate: float = Field(ge=0, le=1)
    payment_fee_rate: float = Field(ge=0, le=1)
    fulfillment_fee: float = Field(ge=0)
    ad_cost_per_unit: float = Field(ge=0)
    return_rate: float = Field(ge=0, le=1)
    target_price: float = Field(gt=0)


class ProfitEstimate(BaseModel):
    landed_cost: float
    fixed_cost_per_unit: float
    variable_rate: float
    break_even_price: float
    contribution_margin: float
    contribution_margin_rate: float
    profit_risk: str


def _round_money(value: float) -> float:
    return round(value + 1e-9, 2)


def estimate_profit(data: ProfitInput) -> ProfitEstimate:
    landed_cost = data.unit_cost + data.shipping_cost + (data.unit_cost * data.duty_rate)
    fixed_cost = landed_cost + data.fulfillment_fee + data.ad_cost_per_unit
    variable_rate = data.marketplace_fee_rate + data.payment_fee_rate + data.return_rate
    contribution_rate = 1 - variable_rate
    if contribution_rate <= 0:
        break_even_price = float("inf")
        contribution_margin = -fixed_cost
        contribution_margin_rate = -1.0
    else:
        break_even_price = fixed_cost / contribution_rate
        contribution_margin = (data.target_price * contribution_rate) - fixed_cost
        contribution_margin_rate = contribution_margin / data.target_price

    if contribution_margin_rate < 0.15:
        profit_risk = "high"
    elif contribution_margin_rate < 0.25:
        profit_risk = "medium"
    else:
        profit_risk = "low"

    return ProfitEstimate(
        landed_cost=_round_money(landed_cost),
        fixed_cost_per_unit=_round_money(fixed_cost),
        variable_rate=round(variable_rate, 4),
        break_even_price=_round_money(break_even_price),
        contribution_margin=_round_money(contribution_margin),
        contribution_margin_rate=round(contribution_margin_rate, 2),
        profit_risk=profit_risk,
    )

