from fastapi.testclient import TestClient

from app.main import create_app


def test_marketplace_rules_endpoint_returns_amazon_constraints():
    client = TestClient(create_app())

    response = client.get("/marketplaces/amazon/rules")

    assert response.status_code == 200
    data = response.json()
    assert data["marketplace"] == "amazon"
    assert data["max_title_length"] == 200
    assert data["required_bullet_points"] == 3


def test_create_workflow_returns_deterministic_preview():
    client = TestClient(create_app())

    response = client.post(
        "/workflows",
        json={
            "product_idea": "foldable under-bed storage organizer",
            "target_marketplaces": ["amazon", "shopify", "tiktok_shop"],
            "target_price": 29.99,
            "risk_preference": "balanced",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["workflow_id"].startswith("wf_")
    assert data["state"] == "awaiting_approval"
    assert data["approval_required"] is True
    assert data["profit_estimate"]["landed_cost"] == 12.8
    assert len(data["listing_validations"]) == 3
    assert {item["marketplace"] for item in data["listing_validations"]} == {
        "amazon",
        "shopify",
        "tiktok_shop",
    }
    assert "publish_listing" in data["approval_reasons"]
