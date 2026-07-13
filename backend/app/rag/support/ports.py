from typing import Protocol, Sequence

from app.domain.support import (
    IngestionResult,
    PlannerDecision,
    RetrievalRequest,
    RetrievalResult,
    SupportChunk,
    SupportRequest,
    SupportSource,
)


class SupportIngestionPort(Protocol):
    def ingest(
        self, source: SupportSource, chunks: Sequence[SupportChunk]
    ) -> IngestionResult: ...

    def tombstone(self, *, tenant_id: str, source_id: str) -> IngestionResult: ...


class SupportRetriever(Protocol):
    def retrieve(self, request: RetrievalRequest) -> RetrievalResult: ...


class SupportPlanner(Protocol):
    def plan(self, request: SupportRequest) -> PlannerDecision: ...
