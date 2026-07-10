from copy import deepcopy
from threading import RLock
from typing import Any

from app.agents.observability.schema import TraceEvent

SECRET_KEY_MARKERS = ("api_key", "secret", "token", "password", "credential")


class TraceEventConflictError(ValueError):
    pass


class TraceEventSecurityError(ValueError):
    pass


class TraceEventRepository:
    def __init__(self) -> None:
        self._events_by_workflow: dict[str, list[TraceEvent]] = {}
        self._lock = RLock()

    def record(self, event: TraceEvent) -> TraceEvent:
        secret_reasons = _secret_metadata_reasons(event.metadata)
        if secret_reasons:
            raise TraceEventSecurityError(secret_reasons[0])

        with self._lock:
            existing = self._events_by_workflow.get(event.workflow_id, [])
            if existing and existing[-1].tenant_id != event.tenant_id:
                raise TraceEventConflictError("tenant mismatch")

            stored = event.model_copy(update={"metadata": deepcopy(event.metadata)}, deep=True)
            self._events_by_workflow[event.workflow_id] = [*existing, stored]
            return stored.model_copy(deep=True)

    def list_by_workflow(self, workflow_id: str, tenant_id: str) -> list[TraceEvent]:
        with self._lock:
            events = self._events_by_workflow.get(workflow_id, [])
            if events and events[-1].tenant_id != tenant_id:
                raise TraceEventConflictError("tenant mismatch")
            return [event.model_copy(deep=True) for event in events]

    def clear(self) -> None:
        with self._lock:
            self._events_by_workflow.clear()


_trace_event_repository = TraceEventRepository()


def get_trace_event_repository() -> TraceEventRepository:
    return _trace_event_repository


def _secret_metadata_reasons(payload: dict[str, Any], prefix: str = "") -> list[str]:
    reasons: list[str] = []
    for key, value in payload.items():
        key_path = f"{prefix}.{key}" if prefix else str(key)
        lower_key = str(key).lower()
        if any(marker in lower_key for marker in SECRET_KEY_MARKERS):
            reasons.append(f"secret-like event metadata key: {key_path}")
        if isinstance(value, dict):
            reasons.extend(_secret_metadata_reasons(value, key_path))
    return reasons
