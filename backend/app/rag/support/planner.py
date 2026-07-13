from __future__ import annotations

from app.domain.support import (
    PlannerDecision,
    RetrievalFilters,
    SupportIntent,
    SupportRequest,
    TransactionToolName,
    TransactionToolRequest,
)


class RuleBasedSupportPlanner:
    _LEGAL_TERMS = (
        " sue ",
        "lawsuit",
        "legal action",
        "attorney",
        "lawyer",
        "起诉",
        "律师",
    )
    _OFF_TOPIC_TERMS = (
        "weather",
        "recipe",
        "sports score",
        "tell me a joke",
        "天气",
        "菜谱",
    )

    def plan(self, request: SupportRequest) -> PlannerDecision:
        query = f" {request.query.casefold()} "
        filters = RetrievalFilters(
            tenant_id=request.tenant_id,
            actor_permission_scopes=request.actor_permission_scopes,
            marketplace=request.marketplace,
            locale=request.locale,
            product_id=request.product_id,
            effective_at=request.effective_at,
        )

        if any(term in query for term in self._LEGAL_TERMS):
            return self._decision(
                request,
                filters,
                intent="legal_threat",
                route="escalate",
                reason_code="legal_threat",
            )
        if any(term in query for term in self._OFF_TOPIC_TERMS):
            return self._decision(
                request,
                filters,
                intent="off_topic",
                route="off_topic",
                reason_code="off_topic",
            )

        # 政策说明优先于金额等交易词，避免“refund policy ... amount”误走实时工具。
        if self._contains_any(
            query,
            ("refund policy", "return policy", "refund eligibility", "return window"),
        ):
            return self._decision(
                request,
                filters,
                intent="refund_policy",
                route="lexical_retrieval",
                reason_code="static_policy_lookup",
            )
        if self._contains_any(
            query,
            ("shipping sla", "shipping time", "delivery estimate", "delivery window"),
        ):
            return self._decision(
                request,
                filters,
                intent="shipping_sla",
                route="lexical_retrieval",
                reason_code="static_policy_lookup",
            )

        transaction = self._transaction_route(query)
        if transaction is not None:
            intent, tool_name = transaction
            return self._decision(
                request,
                filters,
                intent=intent,
                route="requires_transaction_tool",
                reason_code="transaction_tool_required",
                transaction_request=TransactionToolRequest(
                    trace_id=request.trace_id,
                    tenant_id=request.tenant_id,
                    ticket_id=request.ticket_id,
                    tool_name=tool_name,
                    marketplace=request.marketplace,
                    product_id=request.product_id,
                    sku=request.sku,
                ),
            )

        return self._decision(
            request,
            filters,
            intent="knowledge_lookup",
            route="lexical_retrieval",
            reason_code="static_knowledge_lookup",
        )

    @staticmethod
    def _contains_any(query: str, terms: tuple[str, ...]) -> bool:
        return any(term in query for term in terms)

    def _transaction_route(
        self, query: str
    ) -> tuple[SupportIntent, TransactionToolName] | None:
        routes: tuple[
            tuple[tuple[str, ...], SupportIntent, TransactionToolName], ...
        ] = (
            (
                ("shipment tracking", "tracking trajectory", "shipment trajectory", "物流轨迹"),
                "shipment_trajectory",
                "get_shipment_trajectory",
            ),
            (
                ("payment status", "payment go through", "payment went through", "付款状态"),
                "payment_status",
                "get_payment_status",
            ),
            (
                ("refund amount", "money was refunded", "how much was refunded", "退款金额"),
                "refund_amount",
                "get_refund_amount",
            ),
            (
                ("inventory", "in stock", "stock status", "库存"),
                "inventory_status",
                "get_inventory_status",
            ),
            (
                ("coupon", "promo code", "优惠券"),
                "coupon_status",
                "get_coupon_status",
            ),
            (
                ("ticket history", "previous support ticket", "历史工单"),
                "ticket_history",
                "get_ticket_history",
            ),
            (
                ("order status", "status of order", "where is my order", "订单状态"),
                "order_status",
                "get_order_status",
            ),
        )
        for terms, intent, tool_name in routes:
            if self._contains_any(query, terms):
                return intent, tool_name
        return None

    @staticmethod
    def _decision(
        request: SupportRequest,
        filters: RetrievalFilters,
        *,
        intent: SupportIntent,
        route: str,
        reason_code: str,
        transaction_request: TransactionToolRequest | None = None,
    ) -> PlannerDecision:
        return PlannerDecision(
            trace_id=request.trace_id,
            tenant_id=request.tenant_id,
            intent=intent,
            route=route,
            filters=filters,
            transaction_request=transaction_request,
            reason_code=reason_code,
        )
