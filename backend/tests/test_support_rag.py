import hashlib
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.support import (
    RetrievalCandidate,
    RetrievalResult,
    SourceLocator,
    SupportCitation,
    SupportChunk,
    SupportRequest,
    SupportResponse,
    SupportSource,
    SupportTraceSummary,
)
from app.rag.support.lexical import InMemoryLexicalSupportIndex


NOW = datetime(2026, 7, 13, 8, 0, tzinfo=UTC)
CONTENT_HASH = "sha256:" + "a" * 64


def make_locator(**overrides: object) -> SourceLocator:
    values: dict[str, object] = {
        "uri": "mock://support/policies/returns#eligibility",
        "page": None,
        "section_path": ("Returns", "Eligibility"),
        "row": None,
        "timestamp": None,
    }
    values.update(overrides)
    return SourceLocator(**values)


def make_source(**overrides: object) -> SupportSource:
    values: dict[str, object] = {
        "source_id": "src_returns_v1",
        "tenant_id": "tenant_alpha",
        "title": "Return Policy",
        "document_type": "policy",
        "marketplace": "amazon",
        "locale": "en-US",
        "product_id": None,
        "permission_scopes": frozenset({"support:policy"}),
        "policy_version": "returns-2026-07",
        "authority": "authoritative",
        "effective_from": NOW,
        "effective_to": None,
        "content_hash": CONTENT_HASH,
        "index_version": "support-v1",
        "locator": make_locator(),
        "status": "active",
    }
    values.update(overrides)
    return SupportSource(**values)


def make_request(**overrides: object) -> SupportRequest:
    values: dict[str, object] = {
        "trace_id": "trace_001",
        "tenant_id": "tenant_alpha",
        "ticket_id": "ticket_001",
        "query": "What is the return window?",
        "actor_permission_scopes": frozenset({"support:policy"}),
        "marketplace": "amazon",
        "locale": "en-US",
        "product_id": None,
        "sku": None,
        "effective_at": NOW,
    }
    values.update(overrides)
    return SupportRequest(**values)


def hash_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_chunk(**overrides: object) -> SupportChunk:
    text = str(overrides.pop("text", "Returns are accepted within 30 days."))
    values: dict[str, object] = {
        "chunk_id": "chunk_returns_001",
        "parent_id": "parent_returns",
        "source_id": "src_returns_v1",
        "tenant_id": "tenant_alpha",
        "text": text,
        "permission_scopes": frozenset({"support:policy"}),
        "marketplace": "amazon",
        "locale": "en-US",
        "product_id": None,
        "policy_version": "returns-2026-07",
        "authority": "authoritative",
        "effective_from": NOW,
        "effective_to": None,
        "content_hash": hash_text(text),
        "index_version": "support-v1",
        "locator": make_locator(),
    }
    values.update(overrides)
    return SupportChunk(**values)


@pytest.mark.parametrize("field", ["tenant_id", "permission_scopes"])
def test_contract_requires_tenant_and_acl_field(field: str) -> None:
    payload = make_source().model_dump()
    payload.pop(field)

    with pytest.raises(ValidationError):
        SupportSource.model_validate(payload)


def test_locator_rejects_page_zero() -> None:
    with pytest.raises(ValidationError):
        make_locator(page=0)


@pytest.mark.parametrize(
    "overrides",
    [
        {"uri": "not-a-uri"},
        {
            "page": None,
            "section_path": (),
            "row": None,
            "timestamp": None,
        },
    ],
)
def test_locator_rejects_fake_or_unpositioned_value(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        make_locator(**overrides)


def test_contract_rejects_invalid_sha256() -> None:
    with pytest.raises(ValidationError):
        make_source(content_hash="sha256:not-a-real-hash")


@pytest.mark.parametrize(
    ("factory", "field"),
    [
        (make_source, "effective_from"),
        (make_request, "effective_at"),
        (make_locator, "timestamp"),
    ],
)
def test_contract_rejects_naive_datetime(factory: object, field: str) -> None:
    with pytest.raises(ValidationError):
        factory(**{field: datetime(2026, 7, 13, 8, 0)})  # type: ignore[operator]


def test_retrieval_result_rejects_candidate_tenant_mismatch() -> None:
    candidate = RetrievalCandidate(
        chunk_id="chunk_001",
        parent_id=None,
        source_id="src_returns_v1",
        tenant_id="tenant_beta",
        title="Return Policy",
        text="Returns are accepted within 30 days.",
        score=0.8,
        content_hash=CONTENT_HASH,
        index_version="support-v1",
        policy_version="returns-2026-07",
        authority="authoritative",
        locator=make_locator(),
    )

    with pytest.raises(ValidationError):
        RetrievalResult(
            trace_id="trace_001",
            tenant_id="tenant_alpha",
            status="ok",
            candidates=(candidate,),
            index_version="support-v1",
            eligible_count=1,
            stale_filtered_count=0,
            failure_code=None,
        )


def test_response_rejects_nested_tenant_mismatch() -> None:
    citation = SupportCitation(
        citation_number=1,
        source_id="src_returns_v1",
        tenant_id="tenant_beta",
        title="Return Policy",
        locator=make_locator(),
        index_version="support-v1",
        policy_version="returns-2026-07",
    )
    trace = SupportTraceSummary(
        trace_id="trace_001",
        tenant_id="tenant_alpha",
        route="lexical_retrieval",
        index_version="support-v1",
        eligible_count=1,
        candidate_count=1,
        selected_count=1,
        source_ids=("src_returns_v1",),
        scores=(0.8,),
        decision="draft",
        error_categories=(),
    )

    with pytest.raises(ValidationError):
        SupportResponse(
            trace_id="trace_001",
            tenant_id="tenant_alpha",
            status="draft",
            draft="Returns are accepted within 30 days. [1]",
            citations=(citation,),
            transaction_request=None,
            requires_human_review=False,
            reason_code="grounded_draft",
            trace=trace,
        )


def test_ingestion_is_idempotent_by_tenant_source_hash_and_index_version() -> None:
    index = InMemoryLexicalSupportIndex()
    source = make_source()
    chunk = make_chunk()

    first = index.ingest(source, [chunk])
    repeated = index.ingest(source, [chunk])
    other_tenant = index.ingest(
        make_source(tenant_id="tenant_beta"),
        [make_chunk(tenant_id="tenant_beta")],
    )

    assert first.status == "ingested"
    assert repeated.status == "skipped"
    assert repeated.active_chunk_count == 1
    assert other_tenant.status == "ingested"


def test_ingestion_atomically_replaces_version_and_tombstones_old_chunks() -> None:
    index = InMemoryLexicalSupportIndex()
    old_source = make_source()
    old_chunk = make_chunk()
    assert index.ingest(old_source, [old_chunk]).status == "ingested"

    new_text = "The current return window is 45 days."
    new_source = make_source(
        content_hash="sha256:" + "b" * 64,
        index_version="support-v2",
        policy_version="returns-2026-08",
    )
    new_chunk = make_chunk(
        chunk_id="chunk_returns_002",
        text=new_text,
        content_hash=hash_text(new_text),
        index_version="support-v2",
        policy_version="returns-2026-08",
    )

    result = index.ingest(new_source, [new_chunk])

    assert result.status == "ingested"
    assert result.active_chunk_count == 1
    assert tuple(chunk.chunk_id for chunk in index.active_chunks("tenant_alpha", "src_returns_v1")) == (
        "chunk_returns_002",
    )
    assert index.is_chunk_tombstoned("tenant_alpha", "chunk_returns_001") is True


def test_ingestion_failed_version_replacement_keeps_previous_version_active() -> None:
    index = InMemoryLexicalSupportIndex()
    old_source = make_source()
    old_chunk = make_chunk()
    index.ingest(old_source, [old_chunk])
    invalid_chunk = make_chunk(
        chunk_id="chunk_returns_bad",
        index_version="support-v2",
        permission_scopes=frozenset(),
    )

    result = index.ingest(
        make_source(content_hash="sha256:" + "b" * 64, index_version="support-v2"),
        [invalid_chunk],
    )

    assert result.status == "failed"
    assert result.failure_code == "chunk_acl_weaker_than_source"
    assert tuple(chunk.chunk_id for chunk in index.active_chunks("tenant_alpha", "src_returns_v1")) == (
        "chunk_returns_001",
    )


def test_tombstone_is_tenant_scoped_and_repeated_call_is_skipped() -> None:
    index = InMemoryLexicalSupportIndex()
    index.ingest(make_source(), [make_chunk()])
    index.ingest(
        make_source(tenant_id="tenant_beta"),
        [make_chunk(tenant_id="tenant_beta")],
    )

    first = index.tombstone(tenant_id="tenant_alpha", source_id="src_returns_v1")
    repeated = index.tombstone(tenant_id="tenant_alpha", source_id="src_returns_v1")

    assert first.status == "tombstoned"
    assert repeated.status == "skipped"
    assert index.active_chunks("tenant_alpha", "src_returns_v1") == ()
    assert len(index.active_chunks("tenant_beta", "src_returns_v1")) == 1


@pytest.mark.parametrize(
    ("chunk_overrides", "failure_code"),
    [
        ({"permission_scopes": frozenset()}, "chunk_acl_weaker_than_source"),
        ({"content_hash": CONTENT_HASH}, "chunk_hash_mismatch"),
    ],
)
def test_ingestion_rejects_weaker_acl_and_chunk_hash_mismatch(
    chunk_overrides: dict[str, object], failure_code: str
) -> None:
    index = InMemoryLexicalSupportIndex()

    result = index.ingest(make_source(), [make_chunk(**chunk_overrides)])

    assert result.status == "failed"
    assert result.failure_code == failure_code
    assert result.active_chunk_count == 0
