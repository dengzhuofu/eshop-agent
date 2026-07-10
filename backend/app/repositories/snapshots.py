from copy import deepcopy
from datetime import UTC, datetime
from threading import RLock
from typing import Any

from app.domain.snapshots import WorkflowSnapshot

SECRET_KEY_MARKERS = ("api_key", "secret", "token", "password", "credential")


class WorkflowSnapshotConflictError(ValueError):
    pass


class WorkflowSnapshotSecurityError(ValueError):
    pass


class WorkflowSnapshotRepository:
    def __init__(self) -> None:
        self._snapshots_by_workflow: dict[str, list[WorkflowSnapshot]] = {}
        self._lock = RLock()

    def save(
        self,
        workflow_id: str,
        tenant_id: str,
        checkpoint_name: str,
        state: dict[str, Any],
    ) -> WorkflowSnapshot:
        secret_reasons = _secret_state_reasons(state)
        if secret_reasons:
            raise WorkflowSnapshotSecurityError(secret_reasons[0])
        snapshot_state = deepcopy(state)

        with self._lock:
            existing = self._snapshots_by_workflow.get(workflow_id, [])
            if existing and existing[-1].tenant_id != tenant_id:
                raise WorkflowSnapshotConflictError("tenant mismatch")

            if existing and existing[-1].checkpoint_name == checkpoint_name and existing[-1].state == snapshot_state:
                return existing[-1].model_copy(deep=True)

            version = len(existing) + 1
            snapshot = WorkflowSnapshot(
                id=f"snap_{workflow_id}_{version}",
                workflow_id=workflow_id,
                tenant_id=tenant_id,
                checkpoint_name=checkpoint_name,
                version=version,
                state=snapshot_state,
                created_at=datetime.now(UTC),
            )
            self._snapshots_by_workflow[workflow_id] = [*existing, snapshot]
            return snapshot.model_copy(deep=True)

    def get_latest(self, workflow_id: str, tenant_id: str) -> WorkflowSnapshot | None:
        with self._lock:
            snapshots = self._snapshots_by_workflow.get(workflow_id)
            if not snapshots:
                return None
            latest = snapshots[-1]
            if latest.tenant_id != tenant_id:
                raise WorkflowSnapshotConflictError("tenant mismatch")
            return latest.model_copy(deep=True)

    def clear(self) -> None:
        with self._lock:
            self._snapshots_by_workflow.clear()


_workflow_snapshot_repository = WorkflowSnapshotRepository()


def get_workflow_snapshot_repository() -> WorkflowSnapshotRepository:
    return _workflow_snapshot_repository


def _secret_state_reasons(payload: dict[str, Any], prefix: str = "") -> list[str]:
    reasons: list[str] = []
    for key, value in payload.items():
        key_path = f"{prefix}.{key}" if prefix else str(key)
        lower_key = str(key).lower()
        if any(marker in lower_key for marker in SECRET_KEY_MARKERS):
            reasons.append(f"secret-like snapshot key: {key_path}")
        if isinstance(value, dict):
            reasons.extend(_secret_state_reasons(value, key_path))
    return reasons
