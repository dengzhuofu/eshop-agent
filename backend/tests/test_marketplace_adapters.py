import pytest

from app.adapters.mock_marketplaces import get_mock_adapter
from app.domain.enums import Marketplace
from app.domain.schemas import ListingDraft


def test_amazon_adapter_rejects_missing_bullet_points():
    adapter = get_mock_adapter(Marketplace.AMAZON)
    draft = ListingDraft(
        marketplace=Marketplace.AMAZON,
        sku="SKU-1",
        title="Foldable under-bed storage organizer",
        description="Space-saving organizer.",
        bullet_points=[],
        price=29.99,
        attributes={"category": "home_storage"},
    )

    result = adapter.validate_listing(draft)

    assert result.valid is False
    assert any(issue.field == "bullet_points" for issue in result.issues)


def test_amazon_adapter_rejects_overlong_title():
    adapter = get_mock_adapter(Marketplace.AMAZON)
    draft = ListingDraft(
        marketplace=Marketplace.AMAZON,
        sku="SKU-1",
        title="A" * 201,
        description="Space-saving organizer.",
        bullet_points=["Fits under beds", "Foldable", "Breathable fabric"],
        price=29.99,
        attributes={"category": "home_storage"},
    )

    result = adapter.validate_listing(draft)

    assert result.valid is False
    assert any(issue.field == "title" for issue in result.issues)


def test_shopify_adapter_accepts_flexible_listing():
    adapter = get_mock_adapter(Marketplace.SHOPIFY)
    draft = ListingDraft(
        marketplace=Marketplace.SHOPIFY,
        sku="SKU-2",
        title="Foldable under-bed storage organizer",
        description="Space-saving organizer.",
        bullet_points=[],
        price=29.99,
        attributes={"category": "home_storage", "seo_title": "Under-bed organizer"},
    )

    result = adapter.validate_listing(draft)

    assert result.valid is True
    assert result.issues == []


def test_tiktok_shop_adapter_flags_unsupported_claims():
    adapter = get_mock_adapter(Marketplace.TIKTOK_SHOP)
    draft = ListingDraft(
        marketplace=Marketplace.TIKTOK_SHOP,
        sku="SKU-3",
        title="Guaranteed viral storage organizer",
        description="This product guarantees perfect results for every home.",
        bullet_points=["Short video ready"],
        price=24.99,
        attributes={"category": "home_storage", "video_hook": "Transform your room"},
    )

    result = adapter.validate_listing(draft)

    assert result.valid is False
    assert any(issue.field == "claims" for issue in result.issues)


def test_publish_listing_returns_stable_id_for_same_idempotency_key():
    adapter = get_mock_adapter(Marketplace.SHOPIFY)
    draft = ListingDraft(
        marketplace=Marketplace.SHOPIFY,
        sku="SKU-4",
        title="Foldable under-bed storage organizer",
        description="Space-saving organizer.",
        bullet_points=[],
        price=29.99,
        attributes={"category": "home_storage"},
    )

    first = adapter.publish_listing(draft, idempotency_key="same-key")
    second = adapter.publish_listing(draft, idempotency_key="same-key")

    assert first.listing_id == second.listing_id
    assert first.status == "published"


def test_unknown_mock_adapter_is_rejected():
    with pytest.raises(ValueError, match="Unsupported marketplace"):
        get_mock_adapter("unknown")  # type: ignore[arg-type]
