import importlib

import pytest
from pydantic import ValidationError

from app.domain.enums import RiskLevel
from app.domain.schemas import ListingDraft, ValidationResult
from app.services.profit import ProfitEstimate, ProfitInput
from app.services.suppliers import SupplierInput, SupplierScore
from app.tools.registry import ToolDefinition, ToolRegistry, build_default_registry


def _schemas_module():
    try:
        return importlib.import_module("app.tools.schemas")
    except ModuleNotFoundError:
        pytest.fail("app.tools.schemas contract module is missing")


def _tool(name: str) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description="test tool",
        risk_level=RiskLevel.LOW,
        required_permission="workflow:read",
        requires_approval=False,
    )


def test_retry_policy_contract_enforces_bounds_and_forbids_extra_fields():
    schemas = _schemas_module()

    policy = schemas.RetryPolicy(
        max_attempts=5,
        initial_backoff_seconds=5,
        backoff_multiplier=4,
        max_backoff_seconds=30,
        retry_on=frozenset({"transient_error", "timeout"}),
    )

    assert policy.retry_on == frozenset({"transient_error", "timeout"})
    for field, value in (
        ("max_attempts", 0),
        ("max_attempts", 6),
        ("initial_backoff_seconds", -0.1),
        ("backoff_multiplier", 4.1),
        ("max_backoff_seconds", 30.1),
    ):
        payload = policy.model_dump()
        payload[field] = value
        with pytest.raises(ValidationError):
            schemas.RetryPolicy.model_validate(payload)

    with pytest.raises(ValidationError):
        schemas.RetryPolicy.model_validate({**policy.model_dump(), "unexpected": True})


def test_tool_contract_models_forbid_extra_fields():
    schemas = _schemas_module()

    with pytest.raises(ValidationError):
        schemas.ToolRequest(
            request_id="req-1",
            tool_name="estimate_profit",
            tenant_id="tenant-a",
            target_tenant_id="tenant-a",
            workflow_id="wf-1",
            actor_id="actor-1",
            agent_role="profit_analyst",
            trace_id="trace-1",
            actor_permissions={"workflow:read"},
            arguments={},
            unexpected=True,
        )


def test_tool_registry_rejects_duplicate_names():
    with pytest.raises(ValueError, match="Duplicate tool name: duplicate"):
        ToolRegistry([_tool("duplicate"), _tool("duplicate")])


def test_registry_contract_registers_typed_v1_deterministic_tools():
    registry = build_default_registry()
    expected_models = {
        "estimate_profit": (ProfitInput, ProfitEstimate),
        "score_supplier": (SupplierInput, SupplierScore),
        "validate_listing": (ListingDraft, ValidationResult),
    }

    for tool_name, (input_model, output_model) in expected_models.items():
        tool = registry.get(tool_name)
        assert tool.version == "1.0.0"
        assert tool.input_model is input_model
        assert tool.output_model is output_model
        assert tool.timeout_seconds == 5.0
        assert tool.retry_policy.max_attempts == 1
        assert tool.retry_policy.retry_on == frozenset()
        assert tool.audit_policy == "metadata_only"
