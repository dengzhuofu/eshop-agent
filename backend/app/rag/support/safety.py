from __future__ import annotations

import re

from app.domain.support import RetrievalCandidate, RetrievalResult


_INJECTION_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE | re.DOTALL)
    for pattern in (
        r"ignore\s+(?:all\s+)?previous\s+instructions?",
        r"(?:change|override|remove|disable).{0,60}(?:route|filters?|tenant|acl|permissions?|security policy)",
        r"\bcall\s+[a-z][a-z0-9_]{2,}\b",
        r"\bcite\s+\[\d+\]",
        r"\bsystem\s+prompt\b",
    )
)


def is_unsafe_evidence(candidate: RetrievalCandidate) -> bool:
    return any(pattern.search(candidate.text) for pattern in _INJECTION_PATTERNS)


def filter_unsafe_candidates(
    result: RetrievalResult,
) -> tuple[RetrievalResult, int]:
    safe_candidates = tuple(
        candidate
        for candidate in result.candidates
        if not is_unsafe_evidence(candidate)
    )
    removed_count = len(result.candidates) - len(safe_candidates)
    if removed_count == 0:
        return result, 0

    # 文档内容只作为证据；命中指令注入特征的正文在上下文装配前整体移除。
    return result.model_copy(update={"candidates": safe_candidates}), removed_count
