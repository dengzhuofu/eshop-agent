import pytest

from app.domain.enums import RiskLevel
from app.tools.registry import build_default_registry


def test_publish_listing_tool_requires_approval():
    registry = build_default_registry()

    tool = registry.get("publish_listing")

    assert tool.risk_level == RiskLevel.HIGH
    assert tool.requires_approval is True
    assert tool.required_permission == "listing:publish"


def test_read_only_tool_does_not_require_approval():
    registry = build_default_registry()

    tool = registry.get("get_orders")

    assert tool.risk_level == RiskLevel.LOW
    assert tool.requires_approval is False
    assert tool.required_permission == "workflow:read"


def test_unknown_tool_is_rejected():
    registry = build_default_registry()

    with pytest.raises(KeyError, match="Unknown tool"):
        registry.get("missing_tool")

