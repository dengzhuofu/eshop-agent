from app.agents.observability.schema import TraceEventType, create_trace_event
from app.domain.enums import AgentRole
from app.repositories.events import (
    TraceEventConflictError,
    TraceEventRepository,
    TraceEventSecurityError,
)


def test_trace_event_repository_records_events_in_order():
    repo = TraceEventRepository()
    first = create_trace_event(
        "wf_test",
        "tenant-a",
        AgentRole.SUPERVISOR,
        TraceEventType.NODE_END,
        "risk_review",
    )
    second = create_trace_event(
        "wf_test",
        "tenant-a",
        AgentRole.SUPERVISOR,
        TraceEventType.CHECKPOINT,
        "snapshot_saved",
    )

    repo.record(first)
    repo.record(second)

    events = repo.list_by_workflow("wf_test", tenant_id="tenant-a")
    assert [event.name for event in events] == ["risk_review", "snapshot_saved"]


def test_trace_event_repository_enforces_tenant_isolation():
    repo = TraceEventRepository()
    repo.record(
        create_trace_event(
            "wf_test",
            "tenant-a",
            AgentRole.SUPERVISOR,
            TraceEventType.NODE_END,
            "risk_review",
        )
    )

    try:
        repo.list_by_workflow("wf_test", tenant_id="tenant-b")
    except TraceEventConflictError as exc:
        assert "tenant mismatch" in str(exc)
    else:
        raise AssertionError("Expected tenant mismatch to be rejected")


def test_trace_event_repository_rejects_secret_like_metadata():
    repo = TraceEventRepository()
    event = create_trace_event(
        "wf_test",
        "tenant-a",
        AgentRole.SUPERVISOR,
        TraceEventType.NODE_END,
        "risk_review",
        metadata={"api_key": "sk-real-secret"},
    )

    try:
        repo.record(event)
    except TraceEventSecurityError as exc:
        assert "secret-like event metadata key: api_key" in str(exc)
    else:
        raise AssertionError("Expected secret-like event metadata to be rejected")
