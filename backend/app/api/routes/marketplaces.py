from fastapi import APIRouter

from app.domain.enums import Marketplace

router = APIRouter(prefix="/marketplaces", tags=["marketplaces"])

MARKETPLACE_RULES = {
    Marketplace.AMAZON: {
        "marketplace": Marketplace.AMAZON,
        "max_title_length": 200,
        "required_bullet_points": 3,
        "requires_video_hook": False,
        "notes": ["Strict catalog fields", "Amazon-like bullet requirements"],
    },
    Marketplace.SHOPIFY: {
        "marketplace": Marketplace.SHOPIFY,
        "max_title_length": 255,
        "required_bullet_points": 0,
        "requires_video_hook": False,
        "notes": ["Flexible product page", "SEO fields recommended"],
    },
    Marketplace.TIKTOK_SHOP: {
        "marketplace": Marketplace.TIKTOK_SHOP,
        "max_title_length": 120,
        "required_bullet_points": 0,
        "requires_video_hook": True,
        "notes": ["Short commerce content", "Unsupported claims are high risk"],
    },
}


@router.get("/{marketplace}/rules")
def get_marketplace_rules(marketplace: Marketplace) -> dict:
    rules = MARKETPLACE_RULES[marketplace].copy()
    rules["marketplace"] = marketplace.value
    return rules

