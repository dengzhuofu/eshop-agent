from __future__ import annotations

import hashlib

from app.domain.support import (
    AssembledContext,
    ContextBlock,
    RetrievalResult,
    SupportCitation,
)


def assemble_context(
    result: RetrievalResult, *, max_chunks: int, max_chars: int
) -> AssembledContext:
    if max_chunks < 1 or max_chars < 1:
        raise ValueError("context budgets must be positive")

    blocks: list[ContextBlock] = []
    citations: list[SupportCitation] = []
    rendered_parts: list[str] = []
    seen: set[tuple[str, str | None, str]] = set()
    char_count = 0

    for candidate in result.candidates:
        normalized = " ".join(candidate.text.split()).casefold()
        text_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        dedupe_key = (candidate.source_id, candidate.parent_id, text_hash)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        if len(blocks) >= max_chunks:
            break

        citation_number = len(blocks) + 1
        rendered = (
            f"[{citation_number}] {candidate.text}\n"
            f"Source: {candidate.title} ({candidate.locator.uri})"
        )
        separator_size = 2 if rendered_parts else 0
        if char_count + separator_size + len(rendered) > max_chars:
            continue

        rendered_parts.append(rendered)
        char_count += separator_size + len(rendered)
        blocks.append(
            ContextBlock(
                citation_number=citation_number,
                candidate=candidate,
                rendered_text=rendered,
            )
        )
        citations.append(
            SupportCitation(
                citation_number=citation_number,
                source_id=candidate.source_id,
                tenant_id=candidate.tenant_id,
                title=candidate.title,
                locator=candidate.locator,
                index_version=candidate.index_version,
                policy_version=candidate.policy_version,
            )
        )

    return AssembledContext(
        trace_id=result.trace_id,
        tenant_id=result.tenant_id,
        text="\n\n".join(rendered_parts),
        blocks=tuple(blocks),
        citations=tuple(citations),
        char_count=char_count,
    )
