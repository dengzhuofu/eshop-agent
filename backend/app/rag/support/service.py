from __future__ import annotations

from app.config.models import RETRIEVAL_CONFIG
from app.domain.support import (
    RetrievalRequest,
    SupportRequest,
    SupportResponse,
    SupportTraceSummary,
)
from app.rag.support.context import assemble_context
from app.rag.support.ports import SupportPlanner, SupportRetriever


class SupportRagService:
    def __init__(
        self, *, planner: SupportPlanner, retriever: SupportRetriever
    ) -> None:
        self._planner = planner
        self._retriever = retriever

    def answer(self, request: SupportRequest) -> SupportResponse:
        decision = self._planner.plan(request)
        trace = SupportTraceSummary(
            trace_id=request.trace_id,
            tenant_id=request.tenant_id,
            route=decision.route,
            index_version=None,
            eligible_count=0,
            candidate_count=0,
            selected_count=0,
            source_ids=(),
            scores=(),
            decision=decision.reason_code,
            error_categories=(),
        )

        if decision.route == "requires_transaction_tool":
            return SupportResponse(
                trace_id=request.trace_id,
                tenant_id=request.tenant_id,
                status="requires_transaction_tool",
                draft="",
                citations=(),
                transaction_request=decision.transaction_request,
                requires_human_review=False,
                reason_code="transaction_tool_required",
                trace=trace,
            )
        if decision.route == "off_topic":
            return SupportResponse(
                trace_id=request.trace_id,
                tenant_id=request.tenant_id,
                status="off_topic",
                draft="This request is outside the customer-support scope.",
                citations=(),
                transaction_request=None,
                requires_human_review=False,
                reason_code="off_topic",
                trace=trace,
            )
        if decision.route == "escalate":
            return SupportResponse(
                trace_id=request.trace_id,
                tenant_id=request.tenant_id,
                status="escalated",
                draft="This request requires human review.",
                citations=(),
                transaction_request=None,
                requires_human_review=True,
                reason_code=decision.reason_code,
                trace=trace,
            )

        result = self._retriever.retrieve(
            RetrievalRequest(
                trace_id=request.trace_id,
                tenant_id=request.tenant_id,
                query=request.query,
                filters=decision.filters,
                top_k=RETRIEVAL_CONFIG["initial_top_k"],
                score_threshold=RETRIEVAL_CONFIG["score_threshold"],
            )
        )
        context = assemble_context(result, max_chunks=5, max_chars=4000)
        response_trace = SupportTraceSummary(
            trace_id=request.trace_id,
            tenant_id=request.tenant_id,
            route=decision.route,
            index_version=result.index_version,
            eligible_count=result.eligible_count,
            candidate_count=len(result.candidates),
            selected_count=len(context.blocks),
            source_ids=tuple(block.candidate.source_id for block in context.blocks),
            scores=tuple(block.candidate.score for block in context.blocks),
            decision="draft" if context.blocks else "insufficient_evidence",
            error_categories=(result.failure_code,) if result.failure_code else (),
        )
        if not context.blocks:
            return SupportResponse(
                trace_id=request.trace_id,
                tenant_id=request.tenant_id,
                status="insufficient_evidence",
                draft="Available evidence is insufficient; human review is required.",
                citations=(),
                transaction_request=None,
                requires_human_review=True,
                reason_code="insufficient_evidence",
                trace=response_trace,
            )

        draft = "\n".join(
            f"{block.candidate.text} [{block.citation_number}]"
            for block in context.blocks
        )
        return SupportResponse(
            trace_id=request.trace_id,
            tenant_id=request.tenant_id,
            status="draft",
            draft=draft,
            citations=context.citations,
            transaction_request=None,
            requires_human_review=False,
            reason_code="grounded_draft",
            trace=response_trace,
        )
