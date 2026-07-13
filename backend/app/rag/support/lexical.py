from __future__ import annotations

import hashlib
from collections.abc import Sequence

from app.domain.support import IngestionResult, SupportChunk, SupportSource


class InMemoryLexicalSupportIndex:
    def __init__(self) -> None:
        self._sources: dict[tuple[str, str], SupportSource] = {}
        self._chunks: dict[tuple[str, str], SupportChunk] = {}
        self._source_chunks: dict[tuple[str, str], set[str]] = {}
        self._tombstoned_chunks: set[tuple[str, str]] = set()

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
            self._chunks.pop((source.tenant_id, chunk_id), None)
        self._tombstoned_chunks.update(
            (source.tenant_id, chunk_id) for chunk_id in old_chunk_ids - new_chunk_ids
        )
        for chunk in prepared_chunks:
            self._chunks[(source.tenant_id, chunk.chunk_id)] = chunk
            self._tombstoned_chunks.discard((source.tenant_id, chunk.chunk_id))

        self._sources[key] = source
        self._source_chunks[key] = new_chunk_ids
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
