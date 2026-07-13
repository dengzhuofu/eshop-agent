from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from app.domain.enums import Marketplace, RiskLevel
from app.domain.operations import (
    InventoryEvent,
    MetricEvent,
    OperationsRecord,
    OpsActionProposal,
    OpsFailure,
    OrderEvent,
    ShipmentEvent,
)


LISTING_HASH = "a" * 64
OBSERVED_AT = datetime(2026, 7, 13, 10, 0, tzinfo=UTC)
RECEIVED_AT = datetime(2026, 7, 13, 10, 5, tzinfo=UTC)


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
