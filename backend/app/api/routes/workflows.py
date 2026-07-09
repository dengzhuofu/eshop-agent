import hashlib

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.adapters.mock_marketplaces import get_mock_adapter
from app.domain.enums import Marketplace, WorkflowState
from app.domain.schemas import ListingDraft
from app.services.profit import ProfitInput, estimate_profit
from app.tools.registry import build_default_registry

router = APIRouter(prefix="/workflows", tags=["workflows"])


class WorkflowCreateRequest(BaseModel):
    product_idea: str = Field(min_length=1)
    target_marketplaces: list[Marketplace]
    target_price: float = Field(gt=0)
    risk_preference: str = "balanced"


def _workflow_id(request: WorkflowCreateRequest) -> str:
    raw = (
        f"{request.product_idea}:"
        f"{','.join(m.value for m in request.target_marketplaces)}:"
        f"{request.target_price}:"
        f"{request.risk_preference}"
    )
    return f"wf_{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"


def _draft_for_marketplace(marketplace: Marketplace, request: WorkflowCreateRequest) -> ListingDraft:
    attributes: dict[str, str | int | float | bool] = {"category": "home_storage"}
    if marketplace == Marketplace.SHOPIFY:
        attributes["seo_title"] = "Under-bed organizer"
    if marketplace == Marketplace.TIKTOK_SHOP:
        attributes["video_hook"] = "Transform your room"

    return ListingDraft(
        marketplace=marketplace,
        sku=f"SKU-{marketplace.value.upper()}-001",
        title="Foldable under-bed storage organizer",
        description=f"Launch preview for {request.product_idea}.",
        bullet_points=["Fits under beds", "Foldable fabric body", "Easy seasonal storage"],
        price=request.target_price,
        attributes=attributes,
    )


@router.post("")
def create_workflow(request: WorkflowCreateRequest) -> dict:
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
            target_price=request.target_price,
        )
    )
    listing_validations = []
    for marketplace in request.target_marketplaces:
        adapter = get_mock_adapter(marketplace)
        draft = _draft_for_marketplace(marketplace, request)
        validation = adapter.validate_listing(draft)
        listing_validations.append(
            {
                "marketplace": marketplace.value,
                "valid": validation.valid,
                "issues": [issue.model_dump(mode="json") for issue in validation.issues],
            }
        )

    registry = build_default_registry()
    publish_tool = registry.get("publish_listing")
    approval_required = publish_tool.requires_approval

    return {
        "workflow_id": _workflow_id(request),
        "state": WorkflowState.AWAITING_APPROVAL.value,
        "product_idea": request.product_idea,
        "target_marketplaces": [marketplace.value for marketplace in request.target_marketplaces],
        "profit_estimate": profit.model_dump(),
        "listing_validations": listing_validations,
        "approval_required": approval_required,
        "approval_reasons": [publish_tool.name] if approval_required else [],
    }
