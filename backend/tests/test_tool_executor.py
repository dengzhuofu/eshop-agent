import asyncio
import importlib

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from app.domain.enums import AgentRole, ApprovalStatus, RiskLevel
from app.domain.schemas import ListingDraft, ValidationResult
from app.agents.profiles import list_agent_profiles
from app.repositories.approvals import ApprovalRepository
from app.repositories.events import TraceEventRepository
from app.security.boundary import AgentBoundaryPolicy
from app.services.profit import ProfitEstimate, ProfitInput
from app.services.suppliers import SupplierInput, SupplierScore
from app.tools.registry import ToolDefinition, ToolRegistry, build_default_registry
from app.tools.schemas import ToolExecutionContext, ToolRequest


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


def _executor_api():
    try:
        return importlib.import_module("app.tools.executor")
    except ModuleNotFoundError:
        pytest.fail("app.tools.executor module is missing")


def _catalog_api():
    try:
        return importlib.import_module("app.tools.catalog")
    except ModuleNotFoundError:
        pytest.fail("app.tools.catalog module is missing")


def _request(
    tool_name: str,
    arguments: dict,
    *,
    agent_role: AgentRole,
    permissions: set[str] | None = None,
    tenant_id: str = "tenant-a",
    target_tenant_id: str | None = None,
    approval_id: str | None = None,
    idempotency_key: str | None = None,
) -> ToolRequest:
    return ToolRequest(
        request_id=f"req-{tool_name}",
        tool_name=tool_name,
        tenant_id=tenant_id,
        target_tenant_id=target_tenant_id or tenant_id,
        workflow_id="wf-1",
        actor_id="actor-1",
        agent_role=agent_role,
        trace_id="trace-1",
        actor_permissions={"workflow:read"} if permissions is None else permissions,
        arguments=arguments,
        approval_id=approval_id,
        idempotency_key=idempotency_key,
    )


def _context(tool_name: str) -> ToolExecutionContext:
    return ToolExecutionContext(
        request_id=f"req-{tool_name}",
        tenant_id="tenant-a",
        target_tenant_id="tenant-a",
        workflow_id="wf-1",
        actor_id="actor-1",
        agent_role=AgentRole.SUPERVISOR,
        trace_id="trace-1",
    )


def _executor(*, registry=None, handlers=None, approval_verifier=None):
    executor_api = _executor_api()
    catalog_api = _catalog_api()
    registry = registry or build_default_registry()
    return executor_api.ToolExecutor(
        registry=registry,
        handlers=handlers or catalog_api.build_default_handler_catalog(),
        boundary_policy=AgentBoundaryPolicy(list_agent_profiles(), registry),
        approval_verifier=approval_verifier or object(),
        idempotency_store=executor_api.InMemoryIdempotencyStore(),
        trace_repository=TraceEventRepository(),
    )


def _profit_arguments() -> dict:
    return {
        "unit_cost": 8.0,
        "shipping_cost": 4.0,
        "duty_rate": 0.1,
        "marketplace_fee_rate": 0.15,
        "payment_fee_rate": 0.03,
        "fulfillment_fee": 3.0,
        "ad_cost_per_unit": 2.0,
        "return_rate": 0.05,
        "target_price": 29.99,
    }


class ApprovalToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str


class ApprovalToolOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool


def _approval_executor(repository: ApprovalRepository):
    executor_api = _executor_api()
    catalog_api = _catalog_api()
    tool = ToolDefinition(
        name="publish_listing",
        description="approval boundary test tool",
        risk_level=RiskLevel.HIGH,
        required_permission="listing:publish",
        requires_approval=True,
        input_model=ApprovalToolInput,
        output_model=ApprovalToolOutput,
    )
    registry = ToolRegistry([tool])
    catalog = catalog_api.ToolHandlerCatalog()

    async def handler(input_data, context):
        return ApprovalToolOutput(accepted=True)

    catalog.register("publish_listing", handler)
    return _executor(
        registry=registry,
        handlers=catalog,
        approval_verifier=executor_api.RepositoryApprovalProofVerifier(repository),
    )


def _store_approval(
    repository: ApprovalRepository,
    *,
    status: ApprovalStatus = ApprovalStatus.APPROVED,
    tenant_id: str = "tenant-a",
    workflow_id: str = "wf-1",
    tool_name: str = "publish_listing",
    idempotency_key: str | None = None,
) -> str:
    approval_id = "approval-1"
    metadata = {"tool": tool_name}
    if idempotency_key is not None:
        metadata["idempotency_key"] = idempotency_key
    repository.upsert_pending(
        approval_id=approval_id,
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        requested_by="actor-1",
        reason_codes=["high_risk_tool"],
        risk_level=RiskLevel.HIGH,
        resource_type="tool_call",
        resource_id="req-publish_listing",
        metadata=metadata,
    )
    if status == ApprovalStatus.APPROVED:
        repository.approve(approval_id, reviewer_id="reviewer-1")
    elif status == ApprovalStatus.REJECTED:
        repository.reject(approval_id, reviewer_id="reviewer-1")
    return approval_id


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


@pytest.mark.parametrize(
    ("tool_name", "agent_role", "arguments", "expected_key"),
    [
        (
            "estimate_profit",
            AgentRole.PROFIT_ANALYST,
            {
                "unit_cost": 8.0,
                "shipping_cost": 4.0,
                "duty_rate": 0.1,
                "marketplace_fee_rate": 0.15,
                "payment_fee_rate": 0.03,
                "fulfillment_fee": 3.0,
                "ad_cost_per_unit": 2.0,
                "return_rate": 0.05,
                "target_price": 29.99,
            },
            "contribution_margin",
        ),
        (
            "score_supplier",
            AgentRole.SUPPLIER,
            {
                "supplier_id": "SUP-1",
                "unit_price": 8.0,
                "moq": 300,
                "lead_time_days": 14,
                "quality_score": 0.92,
                "defect_rate": 0.02,
                "response_time_hours": 8,
                "has_required_certifications": True,
            },
            "total_score",
        ),
        (
            "validate_listing",
            AgentRole.LISTING,
            {
                "marketplace": "shopify",
                "sku": "SKU-1",
                "title": "Storage organizer",
                "description": "Space-saving organizer.",
                "bullet_points": [],
                "price": 29.99,
                "attributes": {"category": "home_storage"},
            },
            "valid",
        ),
    ],
)
def test_default_handlers_execute_registered_deterministic_tools(
    tool_name,
    agent_role,
    arguments,
    expected_key,
):
    result = asyncio.run(_executor().execute(_request(tool_name, arguments, agent_role=agent_role)))

    assert result.ok is True
    assert expected_key in result.output
    assert result.attempts == 1
    assert result.replayed is False


def test_handler_catalog_rejects_duplicate_registration():
    catalog_api = _catalog_api()
    catalog = catalog_api.ToolHandlerCatalog()

    async def handler(input_data, context):
        return input_data

    catalog.register("estimate_profit", handler)
    with pytest.raises(ValueError, match="Duplicate handler: estimate_profit"):
        catalog.register("estimate_profit", handler)


def test_unknown_tool_returns_normalized_failure():
    result = asyncio.run(
        _executor().execute(
            _request("missing_tool", {}, agent_role=AgentRole.SUPERVISOR)
        )
    )

    assert result.ok is False
    assert result.code == "unknown_tool"
    assert result.tool_version is None
    assert result.attempts == 0


def test_unbound_handler_returns_normalized_failure():
    result = asyncio.run(
        _executor().execute(
            _request(
                "search_market_trends",
                {},
                agent_role=AgentRole.PRODUCT_RESEARCH,
            )
        )
    )

    assert result.ok is False
    assert result.code == "handler_unavailable"
    assert result.tool_version == "1.0.0"
    assert result.attempts == 0


def test_input_schema_failure_does_not_invoke_handler():
    catalog_api = _catalog_api()
    catalog = catalog_api.ToolHandlerCatalog()
    calls = 0

    async def handler(input_data, context):
        nonlocal calls
        calls += 1
        return ProfitEstimate(
            landed_cost=1,
            fixed_cost_per_unit=1,
            variable_rate=0.1,
            break_even_price=1,
            contribution_margin=1,
            contribution_margin_rate=0.1,
            profit_risk="low",
        )

    catalog.register("estimate_profit", handler)
    request = _request(
        "estimate_profit",
        {"unit_cost": -1},
        agent_role=AgentRole.PROFIT_ANALYST,
    )

    result = asyncio.run(_executor(handlers=catalog).execute(request))

    assert result.ok is False
    assert result.code == "input_validation_error"
    assert result.attempts == 0
    assert calls == 0


def test_output_schema_failure_is_normalized():
    catalog_api = _catalog_api()
    catalog = catalog_api.ToolHandlerCatalog()

    async def invalid_handler(input_data, context):
        return {"landed_cost": "not-a-number"}

    catalog.register("estimate_profit", invalid_handler)
    request = _request(
        "estimate_profit",
        {
            "unit_cost": 8,
            "shipping_cost": 4,
            "duty_rate": 0.1,
            "marketplace_fee_rate": 0.15,
            "payment_fee_rate": 0.03,
            "fulfillment_fee": 3,
            "ad_cost_per_unit": 2,
            "return_rate": 0.05,
            "target_price": 29.99,
        },
        agent_role=AgentRole.PROFIT_ANALYST,
    )

    result = asyncio.run(_executor(handlers=catalog).execute(request))

    assert result.ok is False
    assert result.code == "output_validation_error"
    assert result.attempts == 1


def test_access_denied_for_wrong_agent_role():
    request = _request(
        "estimate_profit",
        _profit_arguments(),
        agent_role=AgentRole.PRODUCT_RESEARCH,
    )

    result = asyncio.run(_executor().execute(request))

    assert result.ok is False
    assert result.code == "access_denied"
    assert "not allowed for agent role" in result.details
    assert result.attempts == 0


def test_tenant_mismatch_is_access_denied():
    request = _request(
        "estimate_profit",
        _profit_arguments(),
        agent_role=AgentRole.PROFIT_ANALYST,
        target_tenant_id="tenant-b",
    )

    result = asyncio.run(_executor().execute(request))

    assert result.ok is False
    assert result.code == "access_denied"
    assert "tenant mismatch" in result.details


def test_missing_permission_is_access_denied():
    request = _request(
        "estimate_profit",
        _profit_arguments(),
        agent_role=AgentRole.PROFIT_ANALYST,
        permissions=set(),
    )

    result = asyncio.run(_executor().execute(request))

    assert result.ok is False
    assert result.code == "access_denied"
    assert "missing permission: workflow:read" in result.details


def test_nested_secret_is_denied_before_schema_validation():
    arguments = {**_profit_arguments(), "nested": {"api_token": "must-not-leak"}}
    request = _request(
        "estimate_profit",
        arguments,
        agent_role=AgentRole.PROFIT_ANALYST,
    )

    result = asyncio.run(_executor().execute(request))

    assert result.ok is False
    assert result.code == "access_denied"
    assert result.details == ["secret-like payload key: nested.api_token"]
    assert "must-not-leak" not in result.model_dump_json()


def test_missing_approval_proof_is_required():
    repository = ApprovalRepository()
    request = _request(
        "publish_listing",
        {"value": "payload"},
        agent_role=AgentRole.SUPERVISOR,
        permissions={"listing:publish"},
    )

    result = asyncio.run(_approval_executor(repository).execute(request))

    assert result.ok is False
    assert result.code == "approval_required"
    assert result.retryable is False
    assert result.attempts == 0


@pytest.mark.parametrize(
    ("approval_kwargs", "expected_detail"),
    [
        ({"status": ApprovalStatus.PENDING}, "approval status is not approved"),
        ({"status": ApprovalStatus.REJECTED}, "approval status is not approved"),
        ({"tenant_id": "tenant-b"}, "approval tenant mismatch"),
        ({"workflow_id": "wf-other"}, "approval workflow mismatch"),
        ({"tool_name": "update_price"}, "approval tool mismatch"),
    ],
    ids=["pending", "rejected", "wrong-tenant", "wrong-workflow", "wrong-tool"],
)
def test_approval_proof_must_match_execution_context(approval_kwargs, expected_detail):
    repository = ApprovalRepository()
    approval_id = _store_approval(repository, **approval_kwargs)
    request = _request(
        "publish_listing",
        {"value": "payload"},
        agent_role=AgentRole.SUPERVISOR,
        permissions={"listing:publish"},
        approval_id=approval_id,
    )

    result = asyncio.run(_approval_executor(repository).execute(request))

    assert result.ok is False
    assert result.code == "approval_invalid"
    assert expected_detail in result.details
    assert result.retryable is False
    assert result.attempts == 0


def test_approval_idempotency_key_must_match_when_proof_binds_it():
    repository = ApprovalRepository()
    approval_id = _store_approval(repository, idempotency_key="approved-key")
    request = _request(
        "publish_listing",
        {"value": "payload"},
        agent_role=AgentRole.SUPERVISOR,
        permissions={"listing:publish"},
        approval_id=approval_id,
        idempotency_key="different-key",
    )

    result = asyncio.run(_approval_executor(repository).execute(request))

    assert result.ok is False
    assert result.code == "approval_invalid"
    assert "approval idempotency key mismatch" in result.details


def test_valid_approval_proof_allows_handler_execution():
    repository = ApprovalRepository()
    approval_id = _store_approval(repository, idempotency_key="same-key")
    request = _request(
        "publish_listing",
        {"value": "payload"},
        agent_role=AgentRole.SUPERVISOR,
        permissions={"listing:publish"},
        approval_id=approval_id,
        idempotency_key="same-key",
    )

    result = asyncio.run(_approval_executor(repository).execute(request))

    assert result.ok is True
    assert result.output == {"accepted": True}
    assert result.attempts == 1
