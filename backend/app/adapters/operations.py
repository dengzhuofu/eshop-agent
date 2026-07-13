import json
from pathlib import Path
from typing import Protocol, Self, Sequence

from pydantic import TypeAdapter, ValidationError

from app.domain.operations import (
    InventoryEvent,
    MetricEvent,
    OperationsReadError,
    OperationsReadQuery,
    OperationsRecord,
    OrderEvent,
    ShipmentEvent,
)


class OperationsReadPort(Protocol):
    def read_orders(self, query: OperationsReadQuery) -> list[OrderEvent]: ...

    def read_inventory(self, query: OperationsReadQuery) -> list[InventoryEvent]: ...

    def read_shipments(self, query: OperationsReadQuery) -> list[ShipmentEvent]: ...

    def read_metrics(self, query: OperationsReadQuery) -> list[MetricEvent]: ...


class SeededOperationsReadAdapter:
    def __init__(self, records: Sequence[OperationsRecord]) -> None:
        self._records = tuple(records)

    @classmethod
    def from_directory(cls, directory: Path) -> Self:
        adapter = TypeAdapter(list[OperationsRecord])
        records: list[OperationsRecord] = []
        try:
            for seed_file in sorted(directory.glob("*.json")):
                payload = json.loads(seed_file.read_text(encoding="utf-8"))
                records.extend(adapter.validate_python(payload))
        except (OSError, json.JSONDecodeError, TypeError, ValidationError) as exc:
            # 种子内容视为不可信输入，边界异常只暴露固定错误，不回显原始 payload。
            raise OperationsReadError(
                code="seed_validation_failed",
                message="Operations seed data failed validation.",
            ) from exc
        return cls(records)

    def _filter_query(self, query: OperationsReadQuery) -> list[OperationsRecord]:
        tenant_records = [
            record for record in self._records if record.tenant_id == query.tenant_id
        ]
        if query.marketplaces is not None:
            tenant_records = [
                record for record in tenant_records if record.marketplace in query.marketplaces
            ]
        if query.listing_version_ids is not None:
            tenant_records = [
                record
                for record in tenant_records
                if record.listing_version_id in query.listing_version_ids
            ]
        return tenant_records

    def read_orders(self, query: OperationsReadQuery) -> list[OrderEvent]:
        return [record for record in self._filter_query(query) if isinstance(record, OrderEvent)]

    def read_inventory(self, query: OperationsReadQuery) -> list[InventoryEvent]:
        return [record for record in self._filter_query(query) if isinstance(record, InventoryEvent)]

    def read_shipments(self, query: OperationsReadQuery) -> list[ShipmentEvent]:
        return [record for record in self._filter_query(query) if isinstance(record, ShipmentEvent)]

    def read_metrics(self, query: OperationsReadQuery) -> list[MetricEvent]:
        return [record for record in self._filter_query(query) if isinstance(record, MetricEvent)]


def get_seeded_operations_read_port(
    seed_directory: Path | None = None,
) -> OperationsReadPort:
    directory = seed_directory or Path(__file__).parents[1] / "mock_data" / "operations"
    return SeededOperationsReadAdapter.from_directory(directory)
