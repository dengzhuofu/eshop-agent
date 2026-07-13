import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import TypeAdapter, ValidationError

from app.agents.graphs.operations.routes import route_after_load
from app.agents.graphs.operations.state import create_initial_operations_state
from app.agents.graphs.operations.workflow import run_operations_agent
from app.adapters.operations import SeededOperationsReadAdapter
from app.domain.enums import Marketplace, RiskLevel
from app.domain.operations import (
    FreshnessPolicy,
    InventoryEvent,
    MetricEvent,
    OperationsReadError,
    OperationsReadQuery,
    OperationsRecord,
    OpsActionProposal,
    OpsFailure,
    OrderEvent,
    ShipmentEvent,
)
from app.services.operations import (
    build_operations_read_model,
    detect_ops_anomalies,
    propose_ops_actions,
    summarize_operations,
)


LISTING_HASH = "a" * 64
OBSERVED_AT = datetime(2026, 7, 13, 10, 0, tzinfo=UTC)
RECEIVED_AT = datetime(2026, 7, 13, 10, 5, tzinfo=UTC)
AS_OF = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
SEED_DIRECTORY = Path(__file__).parents[1] / "app" / "mock_data" / "operations"


def _order_event(**overrides) -> OrderEvent:
    payload = {
        "record_type": "order",
        "event_id": "order-event-1",
        "tenant_id": "tenant-a",
        "marketplace": Marketplace.AMAZON,
        "listing_id": "listing-a",
        "listing_version_id": "listing-version-a",
        "listing_content_hash": LISTING_HASH,
        "sku": "SKU-A",
        "observed_at": OBSERVED_AT,
        "received_at": RECEIVED_AT,
        "order_id": "order-1",
        "status": "paid",
        "quantity": 2,
        "gross_revenue": 49.98,
        "currency": "USD",
    }
    payload.update(overrides)
    return OrderEvent.model_validate(payload)


def _inventory_event(**overrides) -> InventoryEvent:
    payload = {
        "record_type": "inventory",
        "event_id": "inventory-event-1",
        "tenant_id": "tenant-a",
        "marketplace": Marketplace.AMAZON,
        "listing_id": "listing-a",
        "listing_version_id": "listing-version-a",
        "listing_content_hash": LISTING_HASH,
        "sku": "SKU-A",
        "observed_at": OBSERVED_AT,
        "received_at": RECEIVED_AT,
        "available_quantity": 5,
        "reserved_quantity": 1,
        "reorder_point": 5,
    }
    payload.update(overrides)
    return InventoryEvent.model_validate(payload)


def _shipment_event(**overrides) -> ShipmentEvent:
    payload = {
        "record_type": "shipment",
        "event_id": "shipment-event-1",
        "tenant_id": "tenant-a",
        "marketplace": Marketplace.SHOPIFY,
        "listing_id": "listing-shopify",
        "listing_version_id": "listing-version-shopify",
        "listing_content_hash": "b" * 64,
        "sku": "SKU-SHOP",
        "observed_at": OBSERVED_AT,
        "received_at": RECEIVED_AT,
        "shipment_id": "shipment-1",
        "order_id": "order-1",
        "status": "delayed",
        "promised_delivery_at": OBSERVED_AT,
        "estimated_delivery_at": OBSERVED_AT + timedelta(hours=24),
    }
    payload.update(overrides)
    return ShipmentEvent.model_validate(payload)


def _metric_event(**overrides) -> MetricEvent:
    payload = {
        "record_type": "metric",
        "event_id": "metric-event-1",
        "tenant_id": "tenant-a",
        "marketplace": Marketplace.TIKTOK_SHOP,
        "listing_id": "listing-tiktok",
        "listing_version_id": "listing-version-tiktok",
        "listing_content_hash": "c" * 64,
        "sku": "SKU-TTS",
        "observed_at": OBSERVED_AT,
        "received_at": RECEIVED_AT,
        "metric_name": "conversion_rate",
        "value": 0.04,
        "window_start": OBSERVED_AT - timedelta(days=1),
        "window_end": OBSERVED_AT,
    }
    payload.update(overrides)
    return MetricEvent.model_validate(payload)


def test_operations_models_require_aware_timestamps_and_version_hash():
    event = _order_event()

    assert event.observed_at == OBSERVED_AT
    assert event.listing_content_hash == LISTING_HASH

    with pytest.raises(ValidationError):
        _order_event(observed_at=OBSERVED_AT.replace(tzinfo=None))

    with pytest.raises(ValidationError):
        _order_event(listing_content_hash="A" * 64)

    with pytest.raises(ValidationError):
        _order_event(unexpected="payload")

    common = {
        "tenant_id": "tenant-a",
        "marketplace": Marketplace.AMAZON,
        "listing_id": "listing-a",
        "listing_version_id": "listing-version-a",
        "listing_content_hash": LISTING_HASH,
        "sku": "SKU-A",
        "observed_at": OBSERVED_AT,
        "received_at": RECEIVED_AT,
    }
    payloads = [
        event.model_dump(mode="json"),
        {
            **common,
            "record_type": "inventory",
            "event_id": "inventory-event-1",
            "available_quantity": 4,
            "reserved_quantity": 1,
            "reorder_point": 5,
        },
        {
            **common,
            "record_type": "shipment",
            "event_id": "shipment-event-1",
            "shipment_id": "shipment-1",
            "order_id": "order-1",
            "status": "in_transit",
            "promised_delivery_at": OBSERVED_AT,
            "estimated_delivery_at": RECEIVED_AT,
        },
        {
            **common,
            "record_type": "metric",
            "event_id": "metric-event-1",
            "metric_name": "conversion_rate",
            "value": 0.04,
            "window_start": OBSERVED_AT,
            "window_end": RECEIVED_AT,
        },
    ]

    records = TypeAdapter(list[OperationsRecord]).validate_python(payloads)

    assert [type(record) for record in records] == [
        OrderEvent,
        InventoryEvent,
        ShipmentEvent,
        MetricEvent,
    ]
    failure = OpsFailure(
        tenant_id="tenant-a",
        code="event_conflict",
        message="Conflicting event IDs were rejected.",
        source_event_ids=["inventory-event-1"],
    )
    assert failure.tenant_id == "tenant-a"

    with pytest.raises(ValidationError):
        MetricEvent.model_validate({**payloads[-1], "window_end": RECEIVED_AT.replace(tzinfo=None)})


def test_action_proposal_is_non_executable():
    payload = {
        "proposal_id": "proposal-1",
        "workflow_id": "workflow-1",
        "tenant_id": "tenant-a",
        "action_type": "replenish_inventory",
        "status": "proposed",
        "execution_allowed": False,
        "approval_required_for_execution": True,
        "risk_level": RiskLevel.HIGH,
        "anomaly_ids": ["anomaly-1"],
        "source_event_ids": ["inventory-event-1"],
        "marketplace": Marketplace.AMAZON,
        "listing_id": "listing-a",
        "listing_version_id": "listing-version-a",
        "listing_content_hash": LISTING_HASH,
        "sku": "SKU-A",
        "rationale": "Review a replenishment action for low stock.",
    }

    proposal = OpsActionProposal.model_validate(payload)

    assert proposal.status == "proposed"
    assert proposal.execution_allowed is False

    with pytest.raises(ValidationError):
        OpsActionProposal.model_validate({**payload, "execution_allowed": True})

    with pytest.raises(ValidationError):
        OpsActionProposal.model_validate({**payload, "status": "approved"})


def test_seeded_port_reads_all_record_types_with_tenant_scope_and_filters():
    port = SeededOperationsReadAdapter.from_directory(SEED_DIRECTORY)
    tenant_query = OperationsReadQuery(tenant_id="tenant-a", as_of=AS_OF)

    orders = port.read_orders(tenant_query)
    inventory = port.read_inventory(tenant_query)
    shipments = port.read_shipments(tenant_query)
    metrics = port.read_metrics(tenant_query)

    assert orders and all(type(item) is OrderEvent for item in orders)
    assert inventory and all(type(item) is InventoryEvent for item in inventory)
    assert shipments and all(type(item) is ShipmentEvent for item in shipments)
    assert metrics and all(type(item) is MetricEvent for item in metrics)
    assert {
        item.tenant_id for item in [*orders, *inventory, *shipments, *metrics]
    } == {"tenant-a"}

    filtered_query = OperationsReadQuery(
        tenant_id="tenant-a",
        as_of=AS_OF,
        marketplaces=[Marketplace.TIKTOK_SHOP],
        listing_version_ids=["lv-a-tiktok-1"],
    )

    assert port.read_orders(filtered_query) == []
    assert port.read_inventory(filtered_query) == []
    assert port.read_shipments(filtered_query) == []
    assert len(port.read_metrics(filtered_query)) == 4
    assert all(
        item.marketplace == Marketplace.TIKTOK_SHOP
        and item.listing_version_id == "lv-a-tiktok-1"
        for item in port.read_metrics(filtered_query)
    )

    tenant_b_query = OperationsReadQuery(tenant_id="tenant-b", as_of=AS_OF)
    assert all(item.tenant_id == "tenant-b" for item in port.read_orders(tenant_b_query))
    assert all(item.tenant_id == "tenant-b" for item in port.read_inventory(tenant_b_query))
    assert all(item.tenant_id == "tenant-b" for item in port.read_shipments(tenant_b_query))
    assert all(item.tenant_id == "tenant-b" for item in port.read_metrics(tenant_b_query))


def test_seed_loader_normalizes_invalid_payload_without_exposure(tmp_path):
    raw_marker = "DO_NOT_EXPOSE_RAW_SEED"
    invalid_record = {
        **_order_event().model_dump(mode="json"),
        "listing_content_hash": raw_marker,
    }
    (tmp_path / "orders.json").write_text(
        json.dumps([invalid_record]),
        encoding="utf-8",
    )

    with pytest.raises(OperationsReadError) as exc_info:
        SeededOperationsReadAdapter.from_directory(tmp_path)

    assert exc_info.value.code == "seed_validation_failed"
    assert exc_info.value.tenant_id == "unknown"
    assert raw_marker not in str(exc_info.value)


def test_read_model_deduplicates_identical_events_and_rejects_conflicts():
    event = _order_event()
    duplicate_port = SeededOperationsReadAdapter([event, event.model_copy(deep=True)])

    read_model = build_operations_read_model(
        duplicate_port,
        OperationsReadQuery(tenant_id="tenant-a", as_of=AS_OF),
    )

    assert [record.event_id for record in read_model.records] == [event.event_id]
    assert [diagnostic.code for diagnostic in read_model.diagnostics] == ["duplicate_ignored"]

    conflicting = event.model_copy(update={"quantity": 3})
    conflict_port = SeededOperationsReadAdapter([event, conflicting])

    with pytest.raises(OperationsReadError) as exc_info:
        build_operations_read_model(
            conflict_port,
            OperationsReadQuery(tenant_id="tenant-a", as_of=AS_OF),
        )

    assert exc_info.value.code == "event_conflict"
    assert exc_info.value.tenant_id == "tenant-a"
    assert exc_info.value.failure.source_event_ids == [event.event_id]


def test_read_model_rejects_cross_tenant_port_and_listing_hash_drift():
    class CrossTenantPort:
        def read_orders(self, query):
            return [_order_event(tenant_id="tenant-b")]

        def read_inventory(self, query):
            return []

        def read_shipments(self, query):
            return []

        def read_metrics(self, query):
            return []

    query = OperationsReadQuery(tenant_id="tenant-a", as_of=AS_OF)
    with pytest.raises(OperationsReadError) as tenant_exc:
        build_operations_read_model(CrossTenantPort(), query)

    assert tenant_exc.value.code == "tenant_mismatch"
    assert tenant_exc.value.tenant_id == "tenant-a"

    first = _inventory_event(event_id="inventory-hash-1")
    drifted = _inventory_event(
        event_id="inventory-hash-2",
        listing_content_hash="d" * 64,
        observed_at=OBSERVED_AT + timedelta(minutes=10),
        received_at=RECEIVED_AT + timedelta(minutes=10),
    )
    with pytest.raises(OperationsReadError) as hash_exc:
        build_operations_read_model(SeededOperationsReadAdapter([first, drifted]), query)

    assert hash_exc.value.code == "listing_version_conflict"
    assert hash_exc.value.failure.listing_version_ids == ["listing-version-a"]

    class MalformedPort:
        def read_orders(self, query):
            return [{"tenant_id": "tenant-a", "raw": "unvalidated"}]

        def read_inventory(self, query):
            return []

        def read_shipments(self, query):
            return []

        def read_metrics(self, query):
            return []

    with pytest.raises(OperationsReadError) as malformed_exc:
        build_operations_read_model(MalformedPort(), query)

    assert malformed_exc.value.code == "source_read_failed"
    assert malformed_exc.value.tenant_id == "tenant-a"


def test_read_model_excludes_future_and_records_freshness_ordering_diagnostics():
    old = _inventory_event(
        event_id="inventory-old",
        observed_at=AS_OF - timedelta(days=1),
        received_at=AS_OF - timedelta(minutes=30),
        available_quantity=100,
    )
    latest = _inventory_event(
        event_id="inventory-latest",
        observed_at=AS_OF - timedelta(hours=1),
        received_at=AS_OF - timedelta(minutes=55),
        available_quantity=5,
    )
    future = _inventory_event(
        event_id="inventory-future",
        observed_at=AS_OF + timedelta(minutes=1),
        received_at=AS_OF + timedelta(minutes=2),
        available_quantity=0,
    )

    read_model = build_operations_read_model(
        SeededOperationsReadAdapter([old, latest, future]),
        OperationsReadQuery(tenant_id="tenant-a", as_of=AS_OF),
    )

    assert [record.event_id for record in read_model.records] == ["inventory-latest"]
    assert [record.event_id for record in read_model.fresh_records] == ["inventory-latest"]
    codes_by_event = {
        diagnostic.event_id: diagnostic.code for diagnostic in read_model.diagnostics
    }
    assert codes_by_event["inventory-future"] == "future_excluded"
    assert {diagnostic.code for diagnostic in read_model.diagnostics if diagnostic.event_id == "inventory-old"} == {
        "late_arrival",
        "out_of_order",
        "stale",
    }


def test_read_model_marks_metric_windows_received_out_of_order():
    newer = _metric_event(
        event_id="metric-newer-window",
        observed_at=AS_OF - timedelta(hours=1),
        received_at=AS_OF - timedelta(minutes=50),
        window_start=AS_OF - timedelta(days=1, hours=1),
        window_end=AS_OF - timedelta(hours=1),
    )
    older_late = _metric_event(
        event_id="metric-older-window-late",
        observed_at=AS_OF - timedelta(days=1),
        received_at=AS_OF - timedelta(minutes=40),
        window_start=AS_OF - timedelta(days=2),
        window_end=AS_OF - timedelta(days=1),
    )

    read_model = build_operations_read_model(
        SeededOperationsReadAdapter([newer, older_late]),
        OperationsReadQuery(tenant_id="tenant-a", as_of=AS_OF),
    )

    assert {record.event_id for record in read_model.records} == {
        "metric-newer-window",
        "metric-older-window-late",
    }
    assert any(
        diagnostic.event_id == "metric-older-window-late"
        and diagnostic.code == "out_of_order"
        for diagnostic in read_model.diagnostics
    )


def test_freshness_policy_includes_exact_boundary_and_marks_older_record_stale():
    exact = _order_event(
        event_id="order-exact",
        order_id="order-exact",
        observed_at=AS_OF - timedelta(seconds=86_400),
        received_at=AS_OF - timedelta(seconds=86_390),
    )
    stale = _order_event(
        event_id="order-stale",
        order_id="order-stale",
        observed_at=AS_OF - timedelta(seconds=86_401),
        received_at=AS_OF - timedelta(seconds=86_391),
    )

    read_model = build_operations_read_model(
        SeededOperationsReadAdapter([exact, stale]),
        OperationsReadQuery(tenant_id="tenant-a", as_of=AS_OF),
        policy=FreshnessPolicy(),
    )

    assert [record.event_id for record in read_model.fresh_records] == ["order-exact"]
    assert [record.event_id for record in read_model.stale_records] == ["order-stale"]


def test_summary_uses_latest_fresh_observations_and_preserves_version_identity():
    read_model = build_operations_read_model(
        SeededOperationsReadAdapter.from_directory(SEED_DIRECTORY),
        OperationsReadQuery(tenant_id="tenant-a", as_of=AS_OF),
    )

    summaries = summarize_operations(read_model)
    summaries_by_version = {summary.listing_version_id: summary for summary in summaries}

    amazon = summaries_by_version["lv-a-amazon-1"]
    assert amazon.tenant_id == "tenant-a"
    assert amazon.listing_content_hash == "a" * 64
    assert amazon.order_count == 1
    assert amazon.units_sold == 2
    assert amazon.gross_revenue == Decimal("59.98")
    assert amazon.available_quantity == 5

    tiktok = summaries_by_version["lv-a-tiktok-1"]
    assert tiktok.conversion_rate == pytest.approx(0.028)
    assert tiktok.return_rate == pytest.approx(0.09)
    assert "metric-a-conversion-current" in tiktok.source_event_ids


def test_anomaly_threshold_equality_and_zero_baseline_are_deterministic():
    baseline_at = AS_OF - timedelta(days=1)
    current_at = AS_OF - timedelta(hours=1)
    records = [
        _inventory_event(observed_at=current_at, received_at=current_at + timedelta(minutes=5)),
        _shipment_event(observed_at=current_at, received_at=current_at + timedelta(minutes=5)),
        _metric_event(
            event_id="conversion-baseline",
            observed_at=baseline_at,
            received_at=baseline_at + timedelta(minutes=5),
            value=0.04,
            window_start=baseline_at - timedelta(days=1),
            window_end=baseline_at,
        ),
        _metric_event(
            event_id="conversion-current",
            observed_at=current_at,
            received_at=current_at + timedelta(minutes=5),
            value=0.032,
            window_start=current_at - timedelta(days=1),
            window_end=current_at,
        ),
        _metric_event(
            event_id="return-baseline",
            observed_at=baseline_at,
            received_at=baseline_at + timedelta(minutes=5),
            metric_name="return_rate",
            value=0.05,
            window_start=baseline_at - timedelta(days=1),
            window_end=baseline_at,
        ),
        _metric_event(
            event_id="return-current",
            observed_at=current_at,
            received_at=current_at + timedelta(minutes=5),
            metric_name="return_rate",
            value=0.08,
            window_start=current_at - timedelta(days=1),
            window_end=current_at,
        ),
        _metric_event(
            event_id="zero-baseline",
            listing_id="listing-zero",
            listing_version_id="listing-version-zero",
            sku="SKU-ZERO",
            observed_at=baseline_at,
            received_at=baseline_at + timedelta(minutes=5),
            value=0,
            window_start=baseline_at - timedelta(days=1),
            window_end=baseline_at,
        ),
        _metric_event(
            event_id="zero-current",
            listing_id="listing-zero",
            listing_version_id="listing-version-zero",
            sku="SKU-ZERO",
            observed_at=current_at,
            received_at=current_at + timedelta(minutes=5),
            value=0,
            window_start=current_at - timedelta(days=1),
            window_end=current_at,
        ),
    ]
    read_model = build_operations_read_model(
        SeededOperationsReadAdapter(records),
        OperationsReadQuery(tenant_id="tenant-a", as_of=AS_OF),
    )

    anomalies, evidence = detect_ops_anomalies(read_model)

    assert {anomaly.anomaly_type for anomaly in anomalies} == {
        "low_stock",
        "shipment_delay",
        "conversion_drop",
        "return_rate_rise",
    }
    assert len(evidence) == len(anomalies) == 4
    assert not any("zero-baseline" in item.source_event_ids for item in anomalies)
    assert all(item.tenant_id == "tenant-a" for item in [*anomalies, *evidence])


def test_anomaly_detection_ignores_stale_data_and_healthy_control():
    port = SeededOperationsReadAdapter.from_directory(SEED_DIRECTORY)
    healthy_model = build_operations_read_model(
        port,
        OperationsReadQuery(tenant_id="tenant-b", as_of=AS_OF),
    )
    stale_low_stock_model = build_operations_read_model(
        SeededOperationsReadAdapter(
            [
                _inventory_event(
                    event_id="stale-low-stock",
                    observed_at=AS_OF - timedelta(days=1),
                    received_at=AS_OF - timedelta(hours=23),
                    available_quantity=0,
                    reorder_point=5,
                )
            ]
        ),
        OperationsReadQuery(tenant_id="tenant-a", as_of=AS_OF),
    )

    assert detect_ops_anomalies(healthy_model) == ([], [])
    assert detect_ops_anomalies(stale_low_stock_model) == ([], [])


def test_proposal_mapping_is_high_risk_non_executable_and_replay_stable():
    read_model = build_operations_read_model(
        SeededOperationsReadAdapter.from_directory(SEED_DIRECTORY),
        OperationsReadQuery(tenant_id="tenant-a", as_of=AS_OF),
    )
    anomalies, _ = detect_ops_anomalies(read_model)

    first = propose_ops_actions(
        workflow_id="workflow-ops-1",
        tenant_id="tenant-a",
        anomalies=anomalies,
    )
    second = propose_ops_actions(
        workflow_id="workflow-ops-1",
        tenant_id="tenant-a",
        anomalies=anomalies,
    )

    assert [proposal.proposal_id for proposal in first] == [
        proposal.proposal_id for proposal in second
    ]
    assert [proposal.action_type for proposal in first].count("optimize_listing") == 2
    assert {proposal.action_type for proposal in first} == {
        "replenish_inventory",
        "review_support_strategy",
        "review_pricing",
        "optimize_listing",
    }
    assert all(
        proposal.status == "proposed"
        and proposal.risk_level == RiskLevel.HIGH
        and proposal.approval_required_for_execution is True
        and proposal.execution_allowed is False
        and proposal.source_event_ids
        and proposal.listing_version_id
        and proposal.listing_content_hash
        for proposal in first
    )


def test_graph_runs_ordered_read_only_steps_with_fresh_evidence_only():
    state = run_operations_agent(
        workflow_id="workflow-graph-1",
        tenant_id="tenant-a",
        as_of=AS_OF,
    )

    assert state["status"] == "completed"
    assert state["current_agent"].value == "ops"
    assert state["completed_steps"] == [
        "load_operations",
        "route",
        "detect_anomalies",
        "propose_actions",
        "complete",
    ]
    assert {item.anomaly_type for item in state["anomalies"]} == {
        "low_stock",
        "shipment_delay",
        "conversion_drop",
        "return_rate_rise",
    }
    assert state["proposals"]
    assert all(proposal.execution_allowed is False for proposal in state["proposals"])
    assert all(
        "inventory-a-amazon-old" not in proposal.source_event_ids
        for proposal in state["proposals"]
    )


def test_graph_returns_insufficient_data_for_empty_and_all_stale_sources():
    empty_state = run_operations_agent(
        workflow_id="workflow-empty",
        tenant_id="tenant-a",
        as_of=AS_OF,
        port=SeededOperationsReadAdapter([]),
    )
    stale_state = run_operations_agent(
        workflow_id="workflow-stale",
        tenant_id="tenant-a",
        as_of=AS_OF,
        port=SeededOperationsReadAdapter(
            [
                _inventory_event(
                    event_id="inventory-all-stale",
                    observed_at=AS_OF - timedelta(days=1),
                    received_at=AS_OF - timedelta(hours=23),
                    available_quantity=0,
                )
            ]
        ),
    )

    for state in (empty_state, stale_state):
        assert state["status"] == "insufficient_data"
        assert state["completed_steps"] == ["load_operations", "route", "complete"]
        assert state["anomalies"] == []
        assert state["evidence"] == []
        assert state["proposals"] == []
        assert state["failure"] is None


def test_graph_normalizes_port_failure_without_proposals():
    class ExplodingPort:
        def read_orders(self, query):
            raise RuntimeError("RAW_PLATFORM_SECRET_SHOULD_NOT_ESCAPE")

        def read_inventory(self, query):
            return []

        def read_shipments(self, query):
            return []

        def read_metrics(self, query):
            return []

    state = run_operations_agent(
        workflow_id="workflow-failed",
        tenant_id="tenant-a",
        as_of=AS_OF,
        port=ExplodingPort(),
    )

    assert state["status"] == "failed"
    assert state["completed_steps"] == ["load_operations", "route", "complete"]
    assert state["failure"].tenant_id == "tenant-a"
    assert state["failure"].code == "source_read_failed"
    assert "RAW_PLATFORM_SECRET" not in state["failure"].message
    assert state["anomalies"] == []
    assert state["proposals"] == []


def test_graph_route_reads_state_without_mutation():
    state = create_initial_operations_state(
        workflow_id="workflow-route",
        tenant_id="tenant-a",
        query=OperationsReadQuery(tenant_id="tenant-a", as_of=AS_OF),
    )
    state["route_decision"] = "complete"
    before = deepcopy(state)

    decision = route_after_load(state)

    assert decision == "complete"
    assert state == before


def test_trace_summaries_contain_ids_counts_decisions_not_payload():
    state = run_operations_agent(
        workflow_id="workflow-trace",
        tenant_id="tenant-a",
        as_of=AS_OF,
    )

    assert [trace.step for trace in state["trace_summaries"]] == state["completed_steps"]
    serialized = [trace.model_dump(mode="json") for trace in state["trace_summaries"]]
    forbidden_keys = {
        "records",
        "orders",
        "inventory",
        "shipments",
        "metrics",
        "gross_revenue",
        "current_value",
        "baseline_value",
        "rationale",
    }
    assert all(not forbidden_keys.intersection(trace) for trace in serialized)
    assert "gross_revenue" not in json.dumps(serialized)
    assert all(trace["tenant_id"] == "tenant-a" for trace in serialized)


def test_graph_replay_ids_are_deterministic():
    first = run_operations_agent(
        workflow_id="workflow-replay",
        tenant_id="tenant-a",
        as_of=AS_OF,
    )
    second = run_operations_agent(
        workflow_id="workflow-replay",
        tenant_id="tenant-a",
        as_of=AS_OF,
    )

    assert [item.summary_id for item in first["summaries"]] == [
        item.summary_id for item in second["summaries"]
    ]
    assert [item.anomaly_id for item in first["anomalies"]] == [
        item.anomaly_id for item in second["anomalies"]
    ]
    assert [item.evidence_id for item in first["evidence"]] == [
        item.evidence_id for item in second["evidence"]
    ]
    assert [item.proposal_id for item in first["proposals"]] == [
        item.proposal_id for item in second["proposals"]
    ]
    assert [item.trace_id for item in first["trace_summaries"]] == [
        item.trace_id for item in second["trace_summaries"]
    ]
