from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SupportDocumentType = Literal["policy", "product_faq", "shipping_sla", "support_guide"]
SupportMarketplace = Literal["amazon", "shopify", "tiktok_shop"]
SupportAuthority = Literal[
    "authoritative", "advisory", "user_generated", "unverified"
]
SupportIntent = Literal[
    "order_status",
    "shipment_trajectory",
    "payment_status",
    "refund_amount",
    "inventory_status",
    "coupon_status",
    "ticket_history",
    "refund_policy",
    "shipping_sla",
    "product_fact",
    "off_topic",
    "legal_threat",
    "knowledge_lookup",
]
TransactionToolName = Literal[
    "get_order_status",
    "get_shipment_trajectory",
    "get_payment_status",
    "get_refund_amount",
    "get_inventory_status",
    "get_coupon_status",
    "get_ticket_history",
]

_HASH_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_URI_PATTERN = re.compile(r"^[a-z][a-z0-9+.-]*://\S+$")


def _require_aware(value: datetime | None) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError("datetime must be timezone-aware")
    return value


class SupportContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class SourceLocator(SupportContract):
    uri: str = Field(min_length=1)
    page: int | None
    section_path: tuple[str, ...]
    row: int | None
    timestamp: datetime | None

    @field_validator("page", "row")
    @classmethod
    def validate_positive_position(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("locator positions start at one")
        return value

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime | None) -> datetime | None:
        return _require_aware(value)

    @field_validator("section_path")
    @classmethod
    def validate_section_path(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not part.strip() for part in value):
            raise ValueError("section path entries must not be empty")
        return value

    @model_validator(mode="after")
    def validate_real_locator(self) -> SourceLocator:
        if not _URI_PATTERN.fullmatch(self.uri):
            raise ValueError("locator uri must be absolute")
        if not any((self.page, self.section_path, self.row, self.timestamp)):
            raise ValueError("locator requires a real source position")
        return self


class SupportSource(SupportContract):
    source_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    document_type: SupportDocumentType
    marketplace: SupportMarketplace | None
    locale: str = Field(min_length=1)
    product_id: str | None
    permission_scopes: frozenset[str]
    policy_version: str | None
    authority: SupportAuthority
    effective_from: datetime | None
    effective_to: datetime | None
    content_hash: str
    index_version: str = Field(min_length=1)
    locator: SourceLocator
    status: Literal["active", "tombstoned"]

    @field_validator("content_hash")
    @classmethod
    def validate_content_hash(cls, value: str) -> str:
        if not _HASH_PATTERN.fullmatch(value):
            raise ValueError("content hash must be sha256:<64 lowercase hex>")
        return value

    @field_validator("effective_from", "effective_to")
    @classmethod
    def validate_effective_datetime(cls, value: datetime | None) -> datetime | None:
        return _require_aware(value)

    @model_validator(mode="after")
    def validate_effective_range(self) -> SupportSource:
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_from > self.effective_to
        ):
            raise ValueError("effective_from must not follow effective_to")
        return self


class SupportChunk(SupportContract):
    chunk_id: str = Field(min_length=1)
    parent_id: str | None
    source_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    permission_scopes: frozenset[str]
    marketplace: SupportMarketplace | None
    locale: str = Field(min_length=1)
    product_id: str | None
    policy_version: str | None
    authority: SupportAuthority
    effective_from: datetime | None
    effective_to: datetime | None
    content_hash: str
    index_version: str = Field(min_length=1)
    locator: SourceLocator

    @field_validator("content_hash")
    @classmethod
    def validate_content_hash(cls, value: str) -> str:
        if not _HASH_PATTERN.fullmatch(value):
            raise ValueError("content hash must be sha256:<64 lowercase hex>")
        return value

    @field_validator("effective_from", "effective_to")
    @classmethod
    def validate_effective_datetime(cls, value: datetime | None) -> datetime | None:
        return _require_aware(value)

    @model_validator(mode="after")
    def validate_effective_range(self) -> SupportChunk:
        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_from > self.effective_to
        ):
            raise ValueError("effective_from must not follow effective_to")
        return self


class SupportRequest(SupportContract):
    trace_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    ticket_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    actor_permission_scopes: frozenset[str]
    marketplace: SupportMarketplace
    locale: str = Field(min_length=1)
    product_id: str | None
    sku: str | None
    effective_at: datetime

    @field_validator("effective_at")
    @classmethod
    def validate_effective_at(cls, value: datetime) -> datetime:
        validated = _require_aware(value)
        assert validated is not None
        return validated


class RetrievalFilters(SupportContract):
    tenant_id: str = Field(min_length=1)
    actor_permission_scopes: frozenset[str]
    marketplace: SupportMarketplace
    locale: str = Field(min_length=1)
    product_id: str | None
    effective_at: datetime

    @field_validator("effective_at")
    @classmethod
    def validate_effective_at(cls, value: datetime) -> datetime:
        validated = _require_aware(value)
        assert validated is not None
        return validated


class TransactionToolRequest(SupportContract):
    trace_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    ticket_id: str = Field(min_length=1)
    tool_name: TransactionToolName
    marketplace: SupportMarketplace
    product_id: str | None
    sku: str | None


class PlannerDecision(SupportContract):
    trace_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    intent: SupportIntent
    route: Literal[
        "lexical_retrieval", "requires_transaction_tool", "off_topic", "escalate"
    ]
    filters: RetrievalFilters
    transaction_request: TransactionToolRequest | None
    reason_code: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_nested_tenants(self) -> PlannerDecision:
        if self.filters.tenant_id != self.tenant_id:
            raise ValueError("planner filters must use the decision tenant")
        if (
            self.transaction_request is not None
            and self.transaction_request.tenant_id != self.tenant_id
        ):
            raise ValueError("transaction request must use the decision tenant")
        return self


class IngestionResult(SupportContract):
    tenant_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    status: Literal["ingested", "skipped", "tombstoned", "failed"]
    index_version: str = Field(min_length=1)
    active_chunk_count: int = Field(ge=0)
    failure_code: str | None


class RetrievalRequest(SupportContract):
    trace_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    filters: RetrievalFilters
    top_k: int = Field(ge=1)
    score_threshold: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_filter_tenant(self) -> RetrievalRequest:
        if self.filters.tenant_id != self.tenant_id:
            raise ValueError("retrieval filters must use the request tenant")
        return self


class RetrievalCandidate(SupportContract):
    chunk_id: str = Field(min_length=1)
    parent_id: str | None
    source_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    text: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)
    content_hash: str
    index_version: str = Field(min_length=1)
    policy_version: str | None
    authority: SupportAuthority
    locator: SourceLocator

    @field_validator("content_hash")
    @classmethod
    def validate_content_hash(cls, value: str) -> str:
        if not _HASH_PATTERN.fullmatch(value):
            raise ValueError("content hash must be sha256:<64 lowercase hex>")
        return value


class RetrievalResult(SupportContract):
    trace_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    status: Literal["ok", "unavailable"]
    candidates: tuple[RetrievalCandidate, ...]
    index_version: str = Field(min_length=1)
    eligible_count: int = Field(ge=0)
    stale_filtered_count: int = Field(ge=0)
    failure_code: str | None

    @model_validator(mode="after")
    def validate_candidates(self) -> RetrievalResult:
        if any(candidate.tenant_id != self.tenant_id for candidate in self.candidates):
            raise ValueError("retrieval candidates must use the result tenant")
        if self.status == "unavailable" and self.candidates:
            raise ValueError("unavailable retrieval cannot contain candidates")
        return self


class SupportCitation(SupportContract):
    citation_number: int = Field(ge=1)
    source_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    locator: SourceLocator
    index_version: str = Field(min_length=1)
    policy_version: str | None


class ContextBlock(SupportContract):
    citation_number: int = Field(ge=1)
    candidate: RetrievalCandidate
    rendered_text: str = Field(min_length=1)


class AssembledContext(SupportContract):
    trace_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    text: str
    blocks: tuple[ContextBlock, ...]
    citations: tuple[SupportCitation, ...]
    char_count: int = Field(ge=0)


class SupportTraceSummary(SupportContract):
    trace_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    route: Literal[
        "lexical_retrieval", "requires_transaction_tool", "off_topic", "escalate"
    ]
    index_version: str | None
    eligible_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    source_ids: tuple[str, ...]
    scores: tuple[float, ...]
    decision: str = Field(min_length=1)
    error_categories: tuple[str, ...]


class SupportResponse(SupportContract):
    trace_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    status: Literal[
        "draft",
        "requires_transaction_tool",
        "insufficient_evidence",
        "off_topic",
        "escalated",
    ]
    draft: str
    citations: tuple[SupportCitation, ...]
    transaction_request: TransactionToolRequest | None
    requires_human_review: bool
    reason_code: str = Field(min_length=1)
    trace: SupportTraceSummary

    @model_validator(mode="after")
    def validate_nested_contracts(self) -> SupportResponse:
        if self.trace.tenant_id != self.tenant_id or self.trace.trace_id != self.trace_id:
            raise ValueError("response trace must match response ownership")
        if any(citation.tenant_id != self.tenant_id for citation in self.citations):
            raise ValueError("response citations must use the response tenant")
        if self.transaction_request is not None and (
            self.transaction_request.tenant_id != self.tenant_id
            or self.transaction_request.trace_id != self.trace_id
        ):
            raise ValueError("transaction request must match response ownership")
        return self
