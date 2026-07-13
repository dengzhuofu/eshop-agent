import json
import socket
from pathlib import Path

import pytest
from pydantic import ValidationError

import app.agents.evaluation.runner as evaluation_runner
from app.agents.evaluation.results import (
    EvaluationMetric,
    EvaluationResult,
    ProductLaunchEvaluationSummary,
    canonical_summary_hash,
)
from app.agents.evaluation.runner import (
    DEFAULT_EVAL_ROOT,
    EvaluationFixtureError,
    discover_product_launch_fixture_pairs,
    load_product_launch_expectation,
    load_product_launch_scenario,
    run_product_launch_scenario,
    run_product_launch_suite,
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


def _scenario_payload(
    *,
    scenario_id: str = "fixture-a",
    scenario_version: int = 1,
    marketplaces: list[str] | None = None,
    target_price: float = 29.99,
) -> dict:
    return {
        "schema_version": "product-launch-scenario/v1",
        "scenario_id": scenario_id,
        "scenario_version": scenario_version,
        "tenant_id": "tenant_eval",
        "workflow_id": f"wf_{scenario_id}",
        "action": "preview",
        "input": {
            "product_idea": "foldable under-bed storage organizer",
            "marketplaces": marketplaces if marketplaces is not None else ["amazon"],
            "target_locale": "en-US",
            "target_price": target_price,
            "risk_preference": "balanced",
        },
    }


def _expectation_payload(
    *,
    scenario_id: str = "fixture-a",
    scenario_version: int = 1,
) -> dict:
    summary = _evaluation_summary().model_dump(mode="json")
    return {
        "schema_version": "product-launch-expectation/v1",
        "scenario_id": scenario_id,
        "scenario_version": scenario_version,
        "summary_hash": canonical_summary_hash(_evaluation_summary()),
        "summary": summary,
    }


def _write_fixture_pair(
    root: Path,
    stem: str,
    *,
    scenario_id: str = "fixture-a",
    scenario_version: int = 1,
) -> tuple[Path, Path]:
    scenario_dir = root / "scenarios"
    expected_dir = root / "expected"
    scenario_dir.mkdir(parents=True, exist_ok=True)
    expected_dir.mkdir(parents=True, exist_ok=True)
    scenario_path = scenario_dir / f"{stem}.json"
    expected_path = expected_dir / f"{stem}.json"
    scenario_path.write_text(
        json.dumps(
            _scenario_payload(
                scenario_id=scenario_id,
                scenario_version=scenario_version,
            )
        ),
        encoding="utf-8",
    )
    expected_path.write_text(
        json.dumps(
            _expectation_payload(
                scenario_id=scenario_id,
                scenario_version=scenario_version,
            )
        ),
        encoding="utf-8",
    )
    return scenario_path, expected_path


def test_discover_product_launch_fixture_pairs_returns_exactly_seven_sorted_pairs():
    pairs = discover_product_launch_fixture_pairs(DEFAULT_EVAL_ROOT)

    assert [scenario.stem for scenario, _ in pairs] == [
        "v1-adapter-validation-failure",
        "v1-high-risk-supplier",
        "v1-localization-claim",
        "v1-low-profit",
        "v1-missing-approval",
        "v1-tampered-version-hash",
        "v1-three-platform-approved-publish",
    ]
    assert all(scenario.stem == expected.stem for scenario, expected in pairs)


def test_fixture_loader_rejects_malformed_json_and_unknown_fields(tmp_path: Path):
    malformed_path = tmp_path / "malformed.json"
    malformed_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(EvaluationFixtureError, match="malformed JSON"):
        load_product_launch_scenario(malformed_path)

    unknown_field_path = tmp_path / "unknown.json"
    payload = _expectation_payload()
    payload["unexpected"] = True
    unknown_field_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(EvaluationFixtureError, match="unexpected"):
        load_product_launch_expectation(unknown_field_path)


@pytest.mark.parametrize(
    ("marketplaces", "target_price"),
    [
        ([], 29.99),
        (["amazon", "amazon"], 29.99),
        (["amazon"], 0),
        (["amazon"], -1),
    ],
)
def test_scenario_loader_rejects_invalid_marketplaces_or_price(
    tmp_path: Path,
    marketplaces: list[str],
    target_price: float,
):
    path = tmp_path / "invalid-scenario.json"
    path.write_text(
        json.dumps(
            _scenario_payload(
                marketplaces=marketplaces,
                target_price=target_price,
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(EvaluationFixtureError):
        load_product_launch_scenario(path)


@pytest.mark.parametrize("orphan_side", ["scenario", "expected"])
def test_discover_product_launch_fixtures_rejects_orphan_files(
    tmp_path: Path,
    orphan_side: str,
):
    scenario_path, expected_path = _write_fixture_pair(tmp_path, "v1-fixture-a")
    (expected_path if orphan_side == "scenario" else scenario_path).unlink()

    with pytest.raises(EvaluationFixtureError, match="orphan"):
        discover_product_launch_fixture_pairs(tmp_path)


def test_discover_product_launch_fixtures_rejects_duplicate_identity(tmp_path: Path):
    _write_fixture_pair(tmp_path, "v1-fixture-a")
    _write_fixture_pair(tmp_path, "v1-fixture-b")

    with pytest.raises(EvaluationFixtureError, match="duplicate scenario identity"):
        discover_product_launch_fixture_pairs(tmp_path)


@pytest.mark.parametrize(
    ("expected_id", "expected_version"),
    [("fixture-b", 1), ("fixture-a", 2)],
)
def test_discover_product_launch_fixtures_rejects_mismatched_identity(
    tmp_path: Path,
    expected_id: str,
    expected_version: int,
):
    _, expected_path = _write_fixture_pair(tmp_path, "v1-fixture-a")
    expected_path.write_text(
        json.dumps(
            _expectation_payload(
                scenario_id=expected_id,
                scenario_version=expected_version,
            )
        ),
        encoding="utf-8",
    )

    with pytest.raises(EvaluationFixtureError, match="identity mismatch"):
        discover_product_launch_fixture_pairs(tmp_path)


def test_product_launch_suite_matches_all_seven_scenario_outcomes():
    results = run_product_launch_suite()
    by_scenario = {result.scenario_id: result for result in results}

    assert len(results) == 7
    assert all(result.status == "passed" for result in results)
    assert all(metric.passed for result in results for metric in result.metrics)
    assert {
        scenario_id: result.actual_summary.final_state.value
        for scenario_id, result in by_scenario.items()
    } == {
        "adapter-validation-failure": "failed",
        "high-risk-supplier": "awaiting_approval",
        "localization-claim": "awaiting_approval",
        "low-profit": "awaiting_approval",
        "missing-approval": "failed",
        "tampered-version-hash": "failed",
        "three-platform-approved-publish": "completed",
    }
    assert [
        item.external_listing_id
        for item in by_scenario["three-platform-approved-publish"].actual_summary.publish
    ] == [
        "AMAZON-2fd3bc8059",
        "SHOPIFY-eb5e767d9e",
        "TIKTOK_SHOP-7cfa428ece",
    ]
    assert (
        by_scenario["low-profit"].actual_summary.selected_listing_versions[0].content_hash
        == "623cf8e9440f02aa1be0b165cf314ca4c5ed0b1197075da22603b01b3b7ce7f2"
    )
    assert by_scenario["high-risk-supplier"].actual_summary.selected_supplier_id is None
    assert by_scenario["localization-claim"].actual_summary.localization_risk_count == 1
    assert by_scenario["missing-approval"].actual_summary.publish == []
    assert by_scenario["tampered-version-hash"].actual_summary.publish_trace_statuses == []
    assert by_scenario[
        "adapter-validation-failure"
    ].actual_summary.publish_trace_statuses == ["failed"]


def test_product_launch_suite_replay_is_deterministic():
    first = [result.model_dump(mode="json") for result in run_product_launch_suite()]
    second = [result.model_dump(mode="json") for result in run_product_launch_suite()]

    assert first == second


def test_product_launch_suite_makes_no_network_calls(monkeypatch: pytest.MonkeyPatch):
    def deny_network(*args, **kwargs):
        raise AssertionError("network access is forbidden in golden evaluations")

    monkeypatch.setattr(socket, "create_connection", deny_network)
    monkeypatch.setattr(socket.socket, "connect", deny_network)

    assert all(result.status == "passed" for result in run_product_launch_suite())


def test_product_launch_scenario_normalizes_workflow_exceptions(
    monkeypatch: pytest.MonkeyPatch,
):
    scenario_path, expected_path = discover_product_launch_fixture_pairs()[0]
    scenario = load_product_launch_scenario(scenario_path)
    expected = load_product_launch_expectation(expected_path)

    def raise_workflow_error(*args, **kwargs):
        raise RuntimeError("sensitive workflow payload")

    monkeypatch.setattr(
        evaluation_runner,
        "run_product_launch_preview",
        raise_workflow_error,
    )

    result = run_product_launch_scenario(scenario, expected)

    assert result.status == "failed"
    assert result.tenant_id == scenario.tenant_id
    assert result.workflow_id == scenario.workflow_id
    assert result.actual_summary.errors == ["workflow_exception:RuntimeError"]
    assert all("sensitive workflow payload" not in reason for reason in result.failure_reasons)
