import pytest
from pydantic import ValidationError

from app.agents.evaluation.results import (
    EvaluationMetric,
    EvaluationResult,
    ProductLaunchEvaluationSummary,
    canonical_summary_hash,
)


def _evaluation_summary(
    *,
    final_state: str = "awaiting_approval",
    trace_counts: dict[str, int] | None = None,
) -> ProductLaunchEvaluationSummary:
    return ProductLaunchEvaluationSummary(
        tenant_id="tenant_eval",
        workflow_id="wf_eval",
        final_state=final_state,
        risk_level="medium",
        profit_risk_level="low",
        supplier_risk_level="low",
        selected_supplier_id="supplier-001",
        localization_risk_count=0,
        approval_request_id="approval-wf_eval",
        approval_status="pending",
        approval_reasons=["publish_listing"],
        snapshot_id="snap_wf_eval_1",
        snapshot_version=1,
        validation=[],
        selected_listing_versions=[],
        publish=[],
        errors=[],
        trace_counts=trace_counts or {"node_end": 8, "tool_call": 6},
        publish_trace_statuses=[],
    )


def test_evaluation_result_is_tenant_scoped_and_score_bounded():
    result = EvaluationResult(
        schema_version="evaluation-result/v1",
        evaluation_id="eval-001",
        scenario_id="three-platform-approved-publish",
        scenario_version=1,
        tenant_id="tenant_eval",
        workflow_id="wf_eval",
        status="passed",
        score=1.0,
        metrics=[
            EvaluationMetric(
                name="identity_match",
                score=1.0,
                passed=True,
                reason="identity matched",
            )
        ],
        expected_summary_hash="a" * 64,
        actual_summary_hash="a" * 64,
        actual_summary=_evaluation_summary(),
        failure_reasons=[],
    )

    assert result.tenant_id == "tenant_eval"
    assert result.threshold == 1.0
    assert result.metrics[0].threshold == 1.0

    with pytest.raises(ValidationError, match="tenant_id"):
        EvaluationResult.model_validate(
            {**result.model_dump(mode="python"), "tenant_id": ""}
        )

    with pytest.raises(ValidationError, match="score"):
        EvaluationResult.model_validate(
            {**result.model_dump(mode="python"), "score": 1.01}
        )


def test_evaluation_summary_hash_is_canonical_and_deterministic():
    summary = _evaluation_summary(trace_counts={"node_end": 8, "tool_call": 6})
    reordered = _evaluation_summary(trace_counts={"tool_call": 6, "node_end": 8})
    changed = _evaluation_summary(final_state="failed")

    first_hash = canonical_summary_hash(summary)

    assert len(first_hash) == 64
    assert first_hash == canonical_summary_hash(summary)
    assert first_hash == canonical_summary_hash(reordered)
    assert first_hash != canonical_summary_hash(changed)
