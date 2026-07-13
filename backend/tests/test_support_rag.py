from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.domain.support import (
    RetrievalCandidate,
    RetrievalResult,
    SourceLocator,
    SupportCitation,
    SupportRequest,
    SupportResponse,
    SupportSource,
    SupportTraceSummary,
)


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
