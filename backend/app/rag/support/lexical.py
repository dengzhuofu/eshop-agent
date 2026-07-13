from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence

from app.domain.support import (
    IngestionResult,
    RetrievalCandidate,
    RetrievalRequest,
    RetrievalResult,
    SupportChunk,
    SupportSource,
)


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]+", re.IGNORECASE)
_STOP_WORDS = frozenset(
    {
        "a",
        "and",
        "are",
        "does",
        "for",
        "is",
        "my",
        "of",
        "the",
        "this",
        "to",
        "what",
        "within",
        "your",
    }
)


class InMemoryLexicalSupportIndex:
    def __init__(self) -> None:
        self._sources: dict[tuple[str, str], SupportSource] = {}
        self._chunks: dict[tuple[str, str], SupportChunk] = {}
        self._source_chunks: dict[tuple[str, str], set[str]] = {}
        self._tombstoned_chunks: set[tuple[str, str]] = set()
        self._chunk_tokens: dict[tuple[str, str], frozenset[str]] = {}
        self._postings: dict[str, set[tuple[str, str]]] = {}
        self._postings_build_count = 0

    def ingest(
        self, source: SupportSource, chunks: Sequence[SupportChunk]
    ) -> IngestionResult:
        key = (source.tenant_id, source.source_id)
        prepared_chunks = tuple(chunks)
        failure_code = self._validate_batch(source, prepared_chunks)
        if failure_code is not None:
            return self._result(
                source,
                status="failed",
                failure_code=failure_code,
                active_chunk_count=len(self._source_chunks.get(key, set())),
            )

        current = self._sources.get(key)
        if (
            current is not None
            and current.status == "active"
            and current.content_hash == source.content_hash
            and current.index_version == source.index_version
        ):
            return self._result(
                source,
                status="skipped",
                active_chunk_count=len(self._source_chunks.get(key, set())),
            )

        new_chunk_ids = {chunk.chunk_id for chunk in prepared_chunks}
        old_chunk_ids = self._source_chunks.get(key, set()).copy()

        # 整批元数据与哈希已校验后才修改索引，失败版本不会留下半替换状态。
        for chunk_id in old_chunk_ids:
            self._remove_postings((source.tenant_id, chunk_id))
            self._chunks.pop((source.tenant_id, chunk_id), None)
        self._tombstoned_chunks.update(
            (source.tenant_id, chunk_id) for chunk_id in old_chunk_ids - new_chunk_ids
        )
        for chunk in prepared_chunks:
            chunk_key = (source.tenant_id, chunk.chunk_id)
            self._chunks[chunk_key] = chunk
            self._add_postings(chunk_key, chunk)
            self._tombstoned_chunks.discard(chunk_key)

        self._sources[key] = source
        self._source_chunks[key] = new_chunk_ids
        self._postings_build_count += 1
        return self._result(
            source,
            status="ingested",
            active_chunk_count=len(new_chunk_ids),
        )

    def tombstone(self, *, tenant_id: str, source_id: str) -> IngestionResult:
        key = (tenant_id, source_id)
        source = self._sources.get(key)
        if source is None:
            return IngestionResult(
                tenant_id=tenant_id,
                source_id=source_id,
                status="failed",
                index_version="unavailable",
                active_chunk_count=0,
                failure_code="source_not_found",
            )
        if source.status == "tombstoned":
            return self._result(source, status="skipped", active_chunk_count=0)

        chunk_ids = self._source_chunks.pop(key, set())
        for chunk_id in chunk_ids:
            self._remove_postings((tenant_id, chunk_id))
            self._chunks.pop((tenant_id, chunk_id), None)
            self._tombstoned_chunks.add((tenant_id, chunk_id))
        self._sources[key] = source.model_copy(update={"status": "tombstoned"})
        return self._result(source, status="tombstoned", active_chunk_count=0)

    def active_chunks(
        self, tenant_id: str, source_id: str
    ) -> tuple[SupportChunk, ...]:
        chunk_ids = sorted(self._source_chunks.get((tenant_id, source_id), set()))
        return tuple(self._chunks[(tenant_id, chunk_id)] for chunk_id in chunk_ids)

    def is_chunk_tombstoned(self, tenant_id: str, chunk_id: str) -> bool:
        return (tenant_id, chunk_id) in self._tombstoned_chunks

    @property
    def postings_build_count(self) -> int:
        return self._postings_build_count

    def retrieve(self, request: RetrievalRequest) -> RetrievalResult:
        query_tokens = self._tokenize(request.query)
        posting_keys: set[tuple[str, str]] = set()
        for token in query_tokens:
            posting_keys.update(self._postings.get(token, set()))
        eligible_keys: set[tuple[str, str]] = set()
        stale_filtered_count = 0

        # tenant/ACL/业务元数据先生成允许集合，评分器只能接触集合内的 chunk 文本。
        for chunk_key, chunk in self._chunks.items():
            if chunk.tenant_id != request.tenant_id:
                continue
            if not chunk.permission_scopes.issubset(
                request.filters.actor_permission_scopes
            ):
                continue
            if chunk.marketplace not in (None, request.filters.marketplace):
                continue
            if chunk.locale != request.filters.locale:
                continue
            if chunk.product_id not in (None, request.filters.product_id):
                continue
            if (
                chunk.effective_from is not None
                and chunk.effective_from > request.filters.effective_at
            ) or (
                chunk.effective_to is not None
                and chunk.effective_to < request.filters.effective_at
            ):
                if chunk_key in posting_keys:
                    stale_filtered_count += 1
                continue
            eligible_keys.add(chunk_key)

        scored: list[tuple[float, SupportChunk]] = []
        for chunk_key in sorted(posting_keys & eligible_keys):
            chunk = self._chunks[chunk_key]
            score = self._score_chunk(query_tokens, chunk)
            if score >= request.score_threshold:
                scored.append((score, chunk))
        scored.sort(key=lambda item: (-item[0], item[1].chunk_id))

        candidates: list[RetrievalCandidate] = []
        for score, chunk in scored[: request.top_k]:
            source = self._sources[(chunk.tenant_id, chunk.source_id)]
            candidates.append(
                RetrievalCandidate(
                    chunk_id=chunk.chunk_id,
                    parent_id=chunk.parent_id,
                    source_id=chunk.source_id,
                    tenant_id=chunk.tenant_id,
                    title=source.title,
                    text=chunk.text,
                    score=score,
                    content_hash=chunk.content_hash,
                    index_version=chunk.index_version,
                    policy_version=chunk.policy_version,
                    authority=chunk.authority,
                    locator=chunk.locator,
                )
            )

        tenant_versions = {
            source.index_version
            for (tenant_id, _), source in self._sources.items()
            if tenant_id == request.tenant_id and source.status == "active"
        }
        return RetrievalResult(
            trace_id=request.trace_id,
            tenant_id=request.tenant_id,
            status="ok",
            candidates=tuple(candidates),
            index_version=max(tenant_versions, default="unavailable"),
            eligible_count=len(eligible_keys),
            stale_filtered_count=stale_filtered_count,
            failure_code=None,
        )

    def _score_chunk(
        self, query_tokens: frozenset[str], chunk: SupportChunk
    ) -> float:
        if not query_tokens:
            return 0.0
        overlap = query_tokens.intersection(self._chunk_tokens[(chunk.tenant_id, chunk.chunk_id)])
        return len(overlap) / len(query_tokens)

    @staticmethod
    def _tokenize(text: str) -> frozenset[str]:
        return frozenset(
            token
            for token in (match.casefold() for match in _TOKEN_PATTERN.findall(text))
            if token not in _STOP_WORDS
        )

    def _add_postings(
        self, chunk_key: tuple[str, str], chunk: SupportChunk
    ) -> None:
        tokens = self._tokenize(chunk.text)
        self._chunk_tokens[chunk_key] = tokens
        for token in tokens:
            self._postings.setdefault(token, set()).add(chunk_key)

    def _remove_postings(self, chunk_key: tuple[str, str]) -> None:
        for token in self._chunk_tokens.pop(chunk_key, frozenset()):
            keys = self._postings.get(token)
            if keys is None:
                continue
            keys.discard(chunk_key)
            if not keys:
                self._postings.pop(token, None)

    def _validate_batch(
        self, source: SupportSource, chunks: tuple[SupportChunk, ...]
    ) -> str | None:
        if source.status != "active":
            return "source_not_active"
        if not chunks:
            return "empty_chunk_batch"
        if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
            return "duplicate_chunk_id"

        for chunk in chunks:
            if chunk.tenant_id != source.tenant_id:
                return "chunk_tenant_mismatch"
            if chunk.source_id != source.source_id:
                return "chunk_source_mismatch"
            if chunk.index_version != source.index_version:
                return "chunk_index_version_mismatch"
            if not source.permission_scopes.issubset(chunk.permission_scopes):
                # chunk ACL 只能等于或严于 source ACL，防止摄取时把受限文档降级为公开。
                return "chunk_acl_weaker_than_source"
            if chunk.marketplace != source.marketplace:
                return "chunk_marketplace_mismatch"
            if chunk.locale != source.locale:
                return "chunk_locale_mismatch"
            if chunk.product_id != source.product_id:
                return "chunk_product_mismatch"
            if chunk.policy_version != source.policy_version:
                return "chunk_policy_version_mismatch"
            if chunk.authority != source.authority:
                return "chunk_authority_mismatch"
            if chunk.effective_from != source.effective_from:
                return "chunk_effective_from_mismatch"
            if chunk.effective_to != source.effective_to:
                return "chunk_effective_to_mismatch"
            expected_hash = "sha256:" + hashlib.sha256(
                chunk.text.encode("utf-8")
            ).hexdigest()
            if chunk.content_hash != expected_hash:
                return "chunk_hash_mismatch"
        return None

    @staticmethod
    def _result(
        source: SupportSource,
        *,
        status: str,
        active_chunk_count: int,
        failure_code: str | None = None,
    ) -> IngestionResult:
        return IngestionResult(
            tenant_id=source.tenant_id,
            source_id=source.source_id,
            status=status,
            index_version=source.index_version,
            active_chunk_count=active_chunk_count,
            failure_code=failure_code,
        )
