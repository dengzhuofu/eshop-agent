from fastapi.testclient import TestClient

from app.main import create_app


def test_agent_profiles_endpoint_exposes_boundaries():
    client = TestClient(create_app())

    response = client.get("/agents/profiles")

    assert response.status_code == 200
    data = response.json()
    roles = {item["role"] for item in data["profiles"]}
    assert "listing" in roles
    listing = next(item for item in data["profiles"] if item["role"] == "listing")
    assert "create_listing_draft" in listing["allowed_tools"]
    assert "publish_listing" not in listing["allowed_tools"]


def test_agent_access_check_endpoint_is_dry_run_only():
    client = TestClient(create_app())

    response = client.post(
        "/agents/access-check",
        json={
            "agent_role": "listing",
            "tool_name": "publish_listing",
            "actor_tenant_id": "tenant-a",
            "target_tenant_id": "tenant-a",
            "actor_permissions": ["listing:publish"],
            "approved": True,
            "payload": {},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["allowed"] is False
    assert "not allowed for agent role" in data["reasons"]
