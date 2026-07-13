from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.domain.support import SupportChunk, SupportSource


@dataclass(frozen=True)
class SupportCorpus:
    version: str
    sources: tuple[SupportSource, ...]
    chunks: tuple[SupportChunk, ...]

    def chunks_for(self, source: SupportSource) -> tuple[SupportChunk, ...]:
        return tuple(
            chunk
            for chunk in self.chunks
            if chunk.tenant_id == source.tenant_id
            and chunk.source_id == source.source_id
        )


def load_support_corpus(path: Path | None = None) -> SupportCorpus:
    corpus_path = path or Path(__file__).with_name("corpus.json")
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    sources: list[SupportSource] = []
    chunks: list[SupportChunk] = []
    for item in payload["sources"]:
        source = SupportSource.model_validate(item["source"])
        parsed_chunks = tuple(
            SupportChunk.model_validate(chunk) for chunk in item["chunks"]
        )
        sources.append(source)
        chunks.extend(parsed_chunks)
    return SupportCorpus(
        version=str(payload["version"]),
        sources=tuple(sources),
        chunks=tuple(chunks),
    )
