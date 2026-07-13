from __future__ import annotations

from app.domain.support import SupportRequest, SupportResponse, SupportTraceSummary
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

        raise RuntimeError("lexical retrieval response is not implemented")
