from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from typing import Iterable

from pydantic import TypeAdapter

from app.adapters.operations import OperationsReadPort
from app.domain.enums import RiskLevel
from app.domain.operations import (
    ActionType,
    AnomalyThresholds,
    AnomalyType,
    FreshnessPolicy,
    InventoryEvent,
    MetricEvent,
    OperationsDiagnostic,
    OperationsReadError,
    OperationsReadModel,
    OperationsReadQuery,
    OperationsRecord,
    OpsActionProposal,
    OpsAnomaly,
    OpsEvidence,
    OpsPerformanceSummary,
    OrderEvent,
    ShipmentEvent,
)


def _stable_id(prefix: str, *parts: object) -> str:
    material = "|".join(str(part) for part in parts)
    digest = sha256(material.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _latest_key(record: OperationsRecord) -> tuple[datetime, datetime, str]:
    return (record.observed_at, record.received_at, record.event_id)


def _record_sort_key(record: OperationsRecord) -> tuple[str, str, str, datetime, datetime, str]:
    return (
        record.marketplace.value,
        record.listing_version_id,
        record.record_type,
        record.observed_at,
        record.received_at,
        record.event_id,
    )


def _stream_key(record: OperationsRecord) -> tuple[object, ...]:
    identity = (
        record.tenant_id,
        record.marketplace,
        record.listing_version_id,
        record.sku,
        record.record_type,
    )
    if isinstance(record, OrderEvent):
        return (*identity, record.order_id)
    if isinstance(record, InventoryEvent):
        return identity
    if isinstance(record, ShipmentEvent):
        return (*identity, record.shipment_id)
    return (*identity, record.metric_name, record.window_start, record.window_end)


def _diagnostic(record: OperationsRecord, code: str) -> OperationsDiagnostic:
    return OperationsDiagnostic(
        tenant_id=record.tenant_id,
        code=code,
        event_id=record.event_id,
        record_type=record.record_type,
        listing_version_id=record.listing_version_id,
        observed_at=record.observed_at,
        received_at=record.received_at,
    )


def _max_age_seconds(record: OperationsRecord, policy: FreshnessPolicy) -> int:
    if isinstance(record, OrderEvent):
        return policy.order_max_age_seconds
    if isinstance(record, InventoryEvent):
        return policy.inventory_max_age_seconds
    if isinstance(record, ShipmentEvent):
        return policy.shipment_max_age_seconds
    return policy.metric_max_age_seconds


def _is_fresh(record: OperationsRecord, as_of: datetime, policy: FreshnessPolicy) -> bool:
    return (as_of - record.observed_at).total_seconds() <= _max_age_seconds(record, policy)


def _read_all_records(
    port: OperationsReadPort,
    query: OperationsReadQuery,
) -> list[OperationsRecord]:
    try:
        records = [
            *port.read_orders(query),
            *port.read_inventory(query),
            *port.read_shipments(query),
            *port.read_metrics(query),
        ]
        return TypeAdapter(list[OperationsRecord]).validate_python(records)
    except OperationsReadError:
        raise
    except Exception as exc:
        raise OperationsReadError(
            code="source_read_failed",
            tenant_id=query.tenant_id,
            message="Operations source read failed.",
        ) from exc


def _validate_tenant(records: Iterable[OperationsRecord], query: OperationsReadQuery) -> None:
    foreign_event_ids = sorted(
        record.event_id for record in records if record.tenant_id != query.tenant_id
    )
    if foreign_event_ids:
        raise OperationsReadError(
            code="tenant_mismatch",
            tenant_id=query.tenant_id,
            message="Operations source returned records for another tenant.",
            source_event_ids=foreign_event_ids,
        )


def _deduplicate_records(
    records: Iterable[OperationsRecord],
    query: OperationsReadQuery,
) -> tuple[list[OperationsRecord], list[OperationsDiagnostic]]:
    by_event_id: dict[str, OperationsRecord] = {}
    diagnostics: list[OperationsDiagnostic] = []
    for record in records:
        existing = by_event_id.get(record.event_id)
        if existing is None:
            by_event_id[record.event_id] = record
            continue
        if existing == record:
            diagnostics.append(_diagnostic(record, "duplicate_ignored"))
            continue
        raise OperationsReadError(
            code="event_conflict",
            tenant_id=query.tenant_id,
            message="Conflicting records share the same event ID.",
            source_event_ids=[record.event_id],
            listing_version_ids=sorted(
                {existing.listing_version_id, record.listing_version_id}
            ),
        )
    return sorted(by_event_id.values(), key=_record_sort_key), diagnostics


def _validate_listing_versions(
    records: Iterable[OperationsRecord],
    query: OperationsReadQuery,
) -> None:
    versions: dict[str, tuple[object, ...]] = {}
    version_event_ids: dict[str, list[str]] = defaultdict(list)
    for record in records:
        identity = (
            record.marketplace,
            record.listing_id,
            record.listing_content_hash,
            record.sku,
        )
        existing = versions.setdefault(record.listing_version_id, identity)
        version_event_ids[record.listing_version_id].append(record.event_id)
        if existing != identity:
            raise OperationsReadError(
                code="listing_version_conflict",
                tenant_id=query.tenant_id,
                message="Listing version identity changed across operations records.",
                source_event_ids=sorted(version_event_ids[record.listing_version_id]),
                listing_version_ids=[record.listing_version_id],
            )


def _out_of_order_diagnostics(records: list[OperationsRecord]) -> list[OperationsDiagnostic]:
    diagnostics: list[OperationsDiagnostic] = []
    streams: dict[tuple[object, ...], list[OperationsRecord]] = defaultdict(list)
    for record in records:
        streams[_stream_key(record)].append(record)
    for stream_records in streams.values():
        latest_observed_at: datetime | None = None
        for record in sorted(stream_records, key=lambda item: (item.received_at, item.event_id)):
            if latest_observed_at is not None and record.observed_at < latest_observed_at:
                diagnostics.append(_diagnostic(record, "out_of_order"))
            if latest_observed_at is None or record.observed_at > latest_observed_at:
                latest_observed_at = record.observed_at
    return diagnostics


def build_operations_read_model(
    port: OperationsReadPort,
    query: OperationsReadQuery,
    policy: FreshnessPolicy | None = None,
) -> OperationsReadModel:
    selected_policy = policy or FreshnessPolicy()
    source_records = _read_all_records(port, query)

    # 租户校验必须先于版本、时序和业务聚合，避免恶意 port 让跨租户记录进入上下文。
    _validate_tenant(source_records, query)
    records, diagnostics = _deduplicate_records(source_records, query)
    _validate_listing_versions(records, query)

    replay_records: list[OperationsRecord] = []
    for record in records:
        if record.observed_at > query.as_of or record.received_at > query.as_of:
            diagnostics.append(_diagnostic(record, "future_excluded"))
            continue
        replay_records.append(record)
        arrival_delay = (record.received_at - record.observed_at).total_seconds()
        if arrival_delay >= selected_policy.late_arrival_seconds:
            diagnostics.append(_diagnostic(record, "late_arrival"))
        if not _is_fresh(record, query.as_of, selected_policy):
            diagnostics.append(_diagnostic(record, "stale"))

    diagnostics.extend(_out_of_order_diagnostics(replay_records))

    # 每个业务流只保留可回放截面上的最新观察；指标按窗口分流以保留基线与当前值。
    latest_by_stream: dict[tuple[object, ...], OperationsRecord] = {}
    for record in replay_records:
        key = _stream_key(record)
        existing = latest_by_stream.get(key)
        if existing is None or _latest_key(record) > _latest_key(existing):
            latest_by_stream[key] = record

    normalized = sorted(latest_by_stream.values(), key=_record_sort_key)
    fresh_records = [
        record for record in normalized if _is_fresh(record, query.as_of, selected_policy)
    ]
    stale_records = [record for record in normalized if record not in fresh_records]
    diagnostics.sort(key=lambda item: (item.event_id, item.code))
    return OperationsReadModel(
        tenant_id=query.tenant_id,
        as_of=query.as_of,
        records=normalized,
        fresh_records=fresh_records,
        stale_records=stale_records,
        diagnostics=diagnostics,
    )


def _summary_identity(record: OperationsRecord) -> tuple[object, ...]:
    return (
        record.tenant_id,
        record.marketplace,
        record.listing_id,
        record.listing_version_id,
        record.listing_content_hash,
        record.sku,
    )


def summarize_operations(read_model: OperationsReadModel) -> list[OpsPerformanceSummary]:
    grouped: dict[tuple[object, ...], list[OperationsRecord]] = defaultdict(list)
    for record in read_model.fresh_records:
        grouped[_summary_identity(record)].append(record)

    summaries: list[OpsPerformanceSummary] = []
    for identity, records in sorted(grouped.items(), key=lambda item: str(item[0])):
        tenant_id, marketplace, listing_id, version_id, content_hash, sku = identity
        orders = [record for record in records if isinstance(record, OrderEvent)]
        inventory = [record for record in records if isinstance(record, InventoryEvent)]
        metrics = [record for record in records if isinstance(record, MetricEvent)]
        latest_inventory = max(inventory, key=_latest_key) if inventory else None
        latest_metrics: dict[str, MetricEvent] = {}
        for metric in metrics:
            existing = latest_metrics.get(metric.metric_name)
            if existing is None or _latest_key(metric) > _latest_key(existing):
                latest_metrics[metric.metric_name] = metric
        source_event_ids = [
            record.event_id for record in sorted(records, key=_record_sort_key)
        ]
        summaries.append(
            OpsPerformanceSummary(
                summary_id=_stable_id(
                    "summary",
                    tenant_id,
                    marketplace,
                    version_id,
                    content_hash,
                    read_model.as_of.isoformat(),
                ),
                tenant_id=tenant_id,
                marketplace=marketplace,
                listing_id=listing_id,
                listing_version_id=version_id,
                listing_content_hash=content_hash,
                sku=sku,
                as_of=read_model.as_of,
                source_event_ids=source_event_ids,
                order_count=len(orders),
                units_sold=sum(order.quantity for order in orders),
                gross_revenue=sum(
                    (order.gross_revenue for order in orders),
                    start=Decimal("0"),
                ),
                available_quantity=(
                    latest_inventory.available_quantity if latest_inventory else None
                ),
                reserved_quantity=(
                    latest_inventory.reserved_quantity if latest_inventory else None
                ),
                conversion_rate=(
                    latest_metrics["conversion_rate"].value
                    if "conversion_rate" in latest_metrics
                    else None
                ),
                return_rate=(
                    latest_metrics["return_rate"].value
                    if "return_rate" in latest_metrics
                    else None
                ),
            )
        )
    return summaries


def _anomaly_models(
    *,
    anomaly_type: AnomalyType,
    records: list[OperationsRecord],
    detected_at: datetime,
    current_value: float,
    baseline_value: float | None,
    threshold_value: float,
    summary: str,
) -> tuple[OpsAnomaly, OpsEvidence]:
    ordered_records = sorted(records, key=_record_sort_key)
    source_event_ids = [record.event_id for record in ordered_records]
    latest = max(ordered_records, key=_latest_key)
    identity_parts = (
        latest.tenant_id,
        latest.marketplace,
        latest.listing_version_id,
        latest.listing_content_hash,
        anomaly_type,
        *source_event_ids,
    )
    evidence_id = _stable_id("evidence", *identity_parts)
    anomaly_id = _stable_id("anomaly", *identity_parts)
    evidence = OpsEvidence(
        evidence_id=evidence_id,
        tenant_id=latest.tenant_id,
        anomaly_type=anomaly_type,
        marketplace=latest.marketplace,
        listing_id=latest.listing_id,
        listing_version_id=latest.listing_version_id,
        listing_content_hash=latest.listing_content_hash,
        sku=latest.sku,
        source_event_ids=source_event_ids,
        observed_at=latest.observed_at,
        current_value=current_value,
        baseline_value=baseline_value,
        threshold_value=threshold_value,
        summary=summary,
    )
    anomaly = OpsAnomaly(
        anomaly_id=anomaly_id,
        tenant_id=latest.tenant_id,
        anomaly_type=anomaly_type,
        marketplace=latest.marketplace,
        listing_id=latest.listing_id,
        listing_version_id=latest.listing_version_id,
        listing_content_hash=latest.listing_content_hash,
        sku=latest.sku,
        source_event_ids=source_event_ids,
        evidence_ids=[evidence_id],
        detected_at=detected_at,
        summary=summary,
    )
    return anomaly, evidence


def detect_ops_anomalies(
    read_model: OperationsReadModel,
    thresholds: AnomalyThresholds | None = None,
) -> tuple[list[OpsAnomaly], list[OpsEvidence]]:
    selected_thresholds = thresholds or AnomalyThresholds()
    anomalies: list[OpsAnomaly] = []
    evidence: list[OpsEvidence] = []

    # 安全边界：过期记录可以出现在诊断中，但绝不能驱动异常或后续动作建议。
    fresh_records = sorted(read_model.fresh_records, key=_record_sort_key)
    for record in fresh_records:
        if isinstance(record, InventoryEvent) and (
            record.available_quantity <= record.reorder_point
        ):
            anomaly, item = _anomaly_models(
                anomaly_type="low_stock",
                records=[record],
                detected_at=read_model.as_of,
                current_value=float(record.available_quantity),
                baseline_value=None,
                threshold_value=float(record.reorder_point),
                summary="Available inventory is at or below the reorder point.",
            )
            anomalies.append(anomaly)
            evidence.append(item)
        if isinstance(record, ShipmentEvent):
            delay_seconds = (
                record.estimated_delivery_at - record.promised_delivery_at
            ).total_seconds()
            if delay_seconds >= selected_thresholds.shipment_delay_seconds:
                anomaly, item = _anomaly_models(
                    anomaly_type="shipment_delay",
                    records=[record],
                    detected_at=read_model.as_of,
                    current_value=delay_seconds,
                    baseline_value=0,
                    threshold_value=float(selected_thresholds.shipment_delay_seconds),
                    summary="Estimated delivery is delayed beyond the allowed threshold.",
                )
                anomalies.append(anomaly)
                evidence.append(item)

    metric_groups: dict[tuple[object, ...], list[MetricEvent]] = defaultdict(list)
    for record in fresh_records:
        if isinstance(record, MetricEvent):
            metric_groups[
                (
                    record.tenant_id,
                    record.marketplace,
                    record.listing_id,
                    record.listing_version_id,
                    record.listing_content_hash,
                    record.sku,
                    record.metric_name,
                )
            ].append(record)

    epsilon = 1e-12
    for records in metric_groups.values():
        ordered = sorted(records, key=_latest_key)
        if len(ordered) < 2:
            continue
        baseline, current = ordered[-2:]
        if current.metric_name == "conversion_rate" and baseline.value > 0:
            relative_drop = (baseline.value - current.value) / baseline.value
            if relative_drop + epsilon >= selected_thresholds.conversion_relative_drop:
                anomaly, item = _anomaly_models(
                    anomaly_type="conversion_drop",
                    records=[baseline, current],
                    detected_at=read_model.as_of,
                    current_value=current.value,
                    baseline_value=baseline.value,
                    threshold_value=selected_thresholds.conversion_relative_drop,
                    summary="Conversion rate declined relative to the prior window.",
                )
                anomalies.append(anomaly)
                evidence.append(item)
        if current.metric_name == "return_rate":
            absolute_rise = current.value - baseline.value
            if absolute_rise + epsilon >= selected_thresholds.return_rate_absolute_rise:
                anomaly, item = _anomaly_models(
                    anomaly_type="return_rate_rise",
                    records=[baseline, current],
                    detected_at=read_model.as_of,
                    current_value=current.value,
                    baseline_value=baseline.value,
                    threshold_value=selected_thresholds.return_rate_absolute_rise,
                    summary="Return rate increased beyond the allowed threshold.",
                )
                anomalies.append(anomaly)
                evidence.append(item)
    return anomalies, evidence


ACTION_MAPPING: dict[AnomalyType, tuple[tuple[ActionType, str], ...]] = {
    "low_stock": (
        ("replenish_inventory", "Review a replenishment action for low stock."),
    ),
    "shipment_delay": (
        ("review_support_strategy", "Review the customer support strategy for delayed orders."),
    ),
    "conversion_drop": (
        ("review_pricing", "Review pricing as a possible contributor to conversion decline."),
        ("optimize_listing", "Review listing content for conversion optimization."),
    ),
    "return_rate_rise": (
        ("optimize_listing", "Review listing accuracy and content to reduce returns."),
    ),
}


def propose_ops_actions(
    *,
    workflow_id: str,
    tenant_id: str,
    anomalies: list[OpsAnomaly],
) -> list[OpsActionProposal]:
    foreign = sorted(
        anomaly.anomaly_id for anomaly in anomalies if anomaly.tenant_id != tenant_id
    )
    if foreign:
        raise OperationsReadError(
            code="tenant_mismatch",
            tenant_id=tenant_id,
            message="Operations anomalies belong to another tenant.",
        )

    proposals: list[OpsActionProposal] = []
    for anomaly in sorted(anomalies, key=lambda item: (item.anomaly_type, item.anomaly_id)):
        for action_type, rationale in ACTION_MAPPING[anomaly.anomaly_type]:
            proposals.append(
                OpsActionProposal(
                    proposal_id=_stable_id(
                        "proposal",
                        workflow_id,
                        tenant_id,
                        anomaly.anomaly_id,
                        action_type,
                    ),
                    workflow_id=workflow_id,
                    tenant_id=tenant_id,
                    action_type=action_type,
                    status="proposed",
                    execution_allowed=False,
                    approval_required_for_execution=True,
                    risk_level=RiskLevel.HIGH,
                    anomaly_ids=[anomaly.anomaly_id],
                    source_event_ids=anomaly.source_event_ids,
                    marketplace=anomaly.marketplace,
                    listing_id=anomaly.listing_id,
                    listing_version_id=anomaly.listing_version_id,
                    listing_content_hash=anomaly.listing_content_hash,
                    sku=anomaly.sku,
                    rationale=rationale,
                )
            )
    return proposals
