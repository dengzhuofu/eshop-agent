import json
from collections import Counter
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from typing import Any, Iterator, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.agents.graphs.nodes import listings as listing_nodes
from app.agents.graphs.workflows import product_launch as product_launch_workflow
from app.agents.observability.schema import TraceEvent, TraceEventType
from app.agents.evaluation.results import (
    EvaluationMetric,
    EvaluationResult,
    ListingValidationEvaluationSummary,
    PublishEvaluationSummary,
    ProductLaunchEvaluationSummary,
    SelectedListingVersionEvaluationSummary,
    Sha256Hash,
    canonical_summary_hash,
)
from app.domain.enums import Marketplace, RiskLevel, WorkflowState
from app.repositories.approvals import ApprovalRepository
from app.repositories.events import TraceEventRepository
from app.repositories.snapshots import WorkflowSnapshotRepository

run_product_launch_preview = product_launch_workflow.run_product_launch_preview
run_product_launch_publish_resume = product_launch_workflow.run_product_launch_publish_resume

DEFAULT_EVAL_ROOT = Path(__file__).resolve().parents[3] / "evals" / "product_launch"
METRIC_NAMES = (
    "identity_match",
    "state_and_risk_match",
    "approval_and_snapshot_match",
    "listing_version_match",
    "validation_match",
    "publish_match",
    "trace_match",
    "error_match",
)
TRACE_COUNT_KEYS = (
    TraceEventType.NODE_END.value,
    TraceEventType.TOOL_CALL.value,
    TraceEventType.APPROVAL.value,
    TraceEventType.CHECKPOINT.value,
    TraceEventType.ERROR.value,
)
_REPOSITORY_OVERRIDE_LOCK = RLock()


class EvaluationFixtureError(ValueError):
    pass


class EvaluationGateError(RuntimeError):
    pass


class StrictFixtureModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductLaunchScenarioInput(StrictFixtureModel):
    product_idea: str = Field(min_length=1)
    marketplaces: list[Marketplace] = Field(min_length=1)
    target_locale: str = Field(min_length=1)
    target_price: float = Field(gt=0)
    risk_preference: Literal["balanced", "supplier_risk", "localization_risk"]

    @field_validator("marketplaces")
    @classmethod
    def marketplaces_must_be_unique(
        cls,
        marketplaces: list[Marketplace],
    ) -> list[Marketplace]:
        if len(marketplaces) != len(set(marketplaces)):
            raise ValueError("marketplaces must not contain duplicates")
        return marketplaces


class ProductLaunchScenario(StrictFixtureModel):
    schema_version: Literal["product-launch-scenario/v1"]
    scenario_id: str = Field(min_length=1)
    scenario_version: int = Field(ge=1)
    tenant_id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    action: Literal[
        "preview",
        "approve_and_resume",
        "remove_approval_then_publish",
        "tamper_approval_hash_then_resume",
    ]
    input: ProductLaunchScenarioInput


class ProductLaunchExpectation(StrictFixtureModel):
    schema_version: Literal["product-launch-expectation/v1"]
    scenario_id: str = Field(min_length=1)
    scenario_version: int = Field(ge=1)
    summary_hash: Sha256Hash
    summary: ProductLaunchEvaluationSummary

    @model_validator(mode="after")
    def summary_hash_must_match_summary(self) -> "ProductLaunchExpectation":
        if self.summary_hash != canonical_summary_hash(self.summary):
            raise ValueError("summary_hash does not match canonical summary")
        return self


@dataclass(slots=True)
class ProductLaunchEvaluationRepositories:
    approvals: ApprovalRepository = field(default_factory=ApprovalRepository)
    snapshots: WorkflowSnapshotRepository = field(default_factory=WorkflowSnapshotRepository)
    traces: TraceEventRepository = field(default_factory=TraceEventRepository)


def _load_fixture_payload(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvaluationFixtureError(
            f"malformed JSON in fixture {path.name}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise EvaluationFixtureError(
            f"unable to read fixture {path.name}: {type(exc).__name__}"
        ) from exc


def load_product_launch_scenario(path: Path) -> ProductLaunchScenario:
    try:
        return ProductLaunchScenario.model_validate(_load_fixture_payload(path))
    except ValidationError as exc:
        raise EvaluationFixtureError(f"invalid scenario fixture {path.name}: {exc}") from exc


def load_product_launch_expectation(path: Path) -> ProductLaunchExpectation:
    try:
        return ProductLaunchExpectation.model_validate(_load_fixture_payload(path))
    except ValidationError as exc:
        raise EvaluationFixtureError(f"invalid expected fixture {path.name}: {exc}") from exc


def discover_product_launch_fixture_pairs(
    root: Path = DEFAULT_EVAL_ROOT,
) -> list[tuple[Path, Path]]:
    scenario_paths = {path.stem: path for path in (root / "scenarios").glob("*.json")}
    expected_paths = {path.stem: path for path in (root / "expected").glob("*.json")}
    orphan_stems = sorted(set(scenario_paths) ^ set(expected_paths))
    if orphan_stems:
        raise EvaluationFixtureError(f"orphan fixture stems: {', '.join(orphan_stems)}")

    pairs: list[tuple[Path, Path]] = []
    seen_identities: set[tuple[str, int]] = set()
    for stem in sorted(scenario_paths):
        scenario_path = scenario_paths[stem]
        expected_path = expected_paths[stem]
        scenario = load_product_launch_scenario(scenario_path)
        expected = load_product_launch_expectation(expected_path)
        identity = (scenario.scenario_id, scenario.scenario_version)
        if identity in seen_identities:
            raise EvaluationFixtureError(
                f"duplicate scenario identity: {scenario.scenario_id} v{scenario.scenario_version}"
            )
        if identity != (expected.scenario_id, expected.scenario_version):
            raise EvaluationFixtureError(f"fixture identity mismatch for stem {stem}")
        seen_identities.add(identity)
        pairs.append((scenario_path, expected_path))
    return pairs


@contextmanager
def _override_product_launch_repositories(
    repositories: ProductLaunchEvaluationRepositories,
) -> Iterator[None]:
    # 现有 workflow 在模块导入时绑定 getter；评估期间需同时替换 workflow 与 node 绑定。
    bindings = (
        (
            product_launch_workflow,
            "get_approval_repository",
            lambda: repositories.approvals,
        ),
        (
            product_launch_workflow,
            "get_workflow_snapshot_repository",
            lambda: repositories.snapshots,
        ),
        (
            product_launch_workflow,
            "get_trace_event_repository",
            lambda: repositories.traces,
        ),
        (listing_nodes, "get_approval_repository", lambda: repositories.approvals),
    )
    with _REPOSITORY_OVERRIDE_LOCK:
        originals = [(module, name, getattr(module, name)) for module, name, _ in bindings]
        try:
            for module, name, replacement in bindings:
                setattr(module, name, replacement)
            yield
        finally:
            for module, name, original in originals:
                setattr(module, name, original)


def _execute_scenario(
    scenario: ProductLaunchScenario,
    repositories: ProductLaunchEvaluationRepositories,
) -> tuple[dict[str, Any], bool]:
    preview = run_product_launch_preview(
        workflow_id=scenario.workflow_id,
        tenant_id=scenario.tenant_id,
        product_idea=scenario.input.product_idea,
        target_marketplaces=scenario.input.marketplaces,
        target_price=scenario.input.target_price,
        risk_preference=scenario.input.risk_preference,
        target_locale=scenario.input.target_locale,
    )
    if scenario.action == "preview":
        return preview, False

    approval_id = preview["approval_request_id"]
    if scenario.action == "remove_approval_then_publish":
        repositories.approvals.clear()
        terminal = run_product_launch_publish_resume(approval_id)
        # 缺失审批的现有恢复入口返回空初始状态；保留 preview 的审计摘要，仅覆盖终态。
        merged = deepcopy(preview)
        merged.update(
            {
                "current_agent": terminal["current_agent"],
                "current_step": terminal["current_step"],
                "errors": terminal["errors"],
                "publish_results": terminal["publish_results"],
            }
        )
        return merged, True

    approval = repositories.approvals.approve(
        approval_id,
        reviewer_id="golden-eval-reviewer",
    )
    if scenario.action == "tamper_approval_hash_then_resume":
        selected_version_id = preview["selected_listing_version_ids"][0]
        approval.metadata["listing_version_hashes"][selected_version_id] = "0" * 64
        repositories.approvals.replace(approval)
    return run_product_launch_publish_resume(approval_id), False


def _scenario_events(
    scenario: ProductLaunchScenario,
    repositories: ProductLaunchEvaluationRepositories,
    include_unknown_failure: bool,
) -> list[TraceEvent]:
    events = repositories.traces.list_by_workflow(
        scenario.workflow_id,
        tenant_id=scenario.tenant_id,
    )
    if include_unknown_failure:
        events.extend(
            repositories.traces.list_by_workflow("unknown", tenant_id="unknown")
        )
    return events


def _summarize_state(
    scenario: ProductLaunchScenario,
    state: dict[str, Any],
    repositories: ProductLaunchEvaluationRepositories,
    *,
    include_unknown_failure: bool = False,
) -> ProductLaunchEvaluationSummary:
    approval_id = state.get("approval_request_id")
    approval = repositories.approvals.get(approval_id)
    snapshot = repositories.snapshots.get_latest(
        scenario.workflow_id,
        tenant_id=scenario.tenant_id,
    )
    events = _scenario_events(scenario, repositories, include_unknown_failure)
    trace_counts = Counter(event.event_type.value for event in events)
    selected_ids = state.get("selected_listing_version_ids", [])
    version_lookup = {
        version.get("version_id"): version
        for version in state.get("listing_versions", [])
        if isinstance(version, dict)
    }
    selected_versions = [version_lookup[version_id] for version_id in selected_ids]
    publish_events = [
        event
        for event in events
        if event.event_type == TraceEventType.TOOL_CALL
        and event.name == "publish_listing"
    ]

    return ProductLaunchEvaluationSummary(
        tenant_id=scenario.tenant_id,
        workflow_id=scenario.workflow_id,
        final_state=WorkflowState(state["current_step"]),
        risk_level=RiskLevel(state["risk_level"]),
        profit_risk_level=RiskLevel(state["profit_estimate"]["profit_risk"]),
        supplier_risk_level=RiskLevel(state["supplier_risk_level"]),
        selected_supplier_id=state.get("selected_supplier_id"),
        localization_risk_count=len(state.get("localization_risk_flags", [])),
        approval_request_id=approval_id,
        approval_status=approval.status.value if approval is not None else None,
        approval_reasons=list(state.get("approval_reasons", [])),
        snapshot_id=snapshot.id if snapshot is not None else None,
        snapshot_version=snapshot.version if snapshot is not None else None,
        validation=[
            ListingValidationEvaluationSummary(
                marketplace=item["marketplace"],
                listing_version_id=item["listing_version_id"],
                valid=item["valid"],
                issue_codes=[str(issue.get("field", "unknown")) for issue in item["issues"]],
            )
            for item in state.get("listing_validations", [])
        ],
        selected_listing_versions=[
            SelectedListingVersionEvaluationSummary(
                marketplace=version["marketplace"],
                version_id=version["version_id"],
                content_hash=version["content_hash"],
                stage=version["stage"],
            )
            for version in selected_versions
        ],
        publish=[
            PublishEvaluationSummary(
                marketplace=item["marketplace"],
                listing_version_id=item["listing_version_id"],
                status="published" if item["status"] == "published" else "failed",
                external_listing_id=item.get("listing_id"),
                error_type=None,
            )
            for item in state.get("publish_results", [])
        ],
        errors=list(state.get("errors", [])),
        trace_counts={key: trace_counts[key] for key in TRACE_COUNT_KEYS},
        publish_trace_statuses=[
            "published" if event.metadata.get("status") == "completed" else "failed"
            for event in publish_events
        ],
    )


def _exception_summary(
    scenario: ProductLaunchScenario,
    repositories: ProductLaunchEvaluationRepositories,
    error_category: str,
) -> ProductLaunchEvaluationSummary:
    events = _scenario_events(scenario, repositories, include_unknown_failure=False)
    trace_counts = Counter(event.event_type.value for event in events)
    return ProductLaunchEvaluationSummary(
        tenant_id=scenario.tenant_id,
        workflow_id=scenario.workflow_id,
        final_state=WorkflowState.FAILED,
        risk_level=RiskLevel.HIGH,
        profit_risk_level=RiskLevel.HIGH,
        supplier_risk_level=RiskLevel.HIGH,
        selected_supplier_id=None,
        localization_risk_count=0,
        approval_request_id=None,
        approval_status=None,
        approval_reasons=[],
        snapshot_id=None,
        snapshot_version=None,
        validation=[],
        selected_listing_versions=[],
        publish=[],
        errors=[error_category],
        trace_counts={key: trace_counts[key] for key in TRACE_COUNT_KEYS},
        publish_trace_statuses=[],
    )


def _comparison_values(
    summary: ProductLaunchEvaluationSummary,
) -> dict[str, object]:
    return {
        "identity_match": (summary.tenant_id, summary.workflow_id),
        "state_and_risk_match": (
            summary.final_state,
            summary.risk_level,
            summary.profit_risk_level,
            summary.supplier_risk_level,
            summary.selected_supplier_id,
            summary.localization_risk_count,
        ),
        "approval_and_snapshot_match": (
            summary.approval_request_id,
            summary.approval_status,
            summary.approval_reasons,
            summary.snapshot_id,
            summary.snapshot_version,
        ),
        "listing_version_match": summary.selected_listing_versions,
        "validation_match": summary.validation,
        "publish_match": summary.publish,
        "trace_match": (summary.trace_counts, summary.publish_trace_statuses),
        "error_match": summary.errors,
    }


def _evaluate_summary(
    scenario: ProductLaunchScenario,
    expected: ProductLaunchExpectation,
    actual: ProductLaunchEvaluationSummary,
    *,
    execution_error: str | None = None,
) -> EvaluationResult:
    expected_values = _comparison_values(expected.summary)
    actual_values = _comparison_values(actual)
    metrics = []
    for name in METRIC_NAMES:
        passed = actual_values[name] == expected_values[name]
        metrics.append(
            EvaluationMetric(
                name=name,
                score=1.0 if passed else 0.0,
                passed=passed,
                reason=f"{name} matched" if passed else f"{name} mismatch",
            )
        )
    score = sum(metric.score for metric in metrics) / len(metrics)
    failure_reasons = [metric.reason for metric in metrics if not metric.passed]
    if execution_error is not None:
        failure_reasons.append(execution_error)
    actual_hash = canonical_summary_hash(actual)
    passed = execution_error is None and all(metric.passed for metric in metrics)
    return EvaluationResult(
        schema_version="evaluation-result/v1",
        evaluation_id=(
            f"eval_{scenario.scenario_id}_v{scenario.scenario_version}_{actual_hash[:12]}"
        ),
        scenario_id=scenario.scenario_id,
        scenario_version=scenario.scenario_version,
        tenant_id=scenario.tenant_id,
        workflow_id=scenario.workflow_id,
        status="passed" if passed else "failed",
        score=score,
        metrics=metrics,
        expected_summary_hash=expected.summary_hash,
        actual_summary_hash=actual_hash,
        actual_summary=actual,
        failure_reasons=failure_reasons,
    )


def run_product_launch_scenario(
    scenario: ProductLaunchScenario,
    expected: ProductLaunchExpectation,
) -> EvaluationResult:
    repositories = ProductLaunchEvaluationRepositories()
    try:
        with _override_product_launch_repositories(repositories):
            state, include_unknown_failure = _execute_scenario(scenario, repositories)
        summary = _summarize_state(
            scenario,
            state,
            repositories,
            include_unknown_failure=include_unknown_failure,
        )
        return _evaluate_summary(scenario, expected, summary)
    except Exception as exc:
        # 编排异常只暴露类型，不把可能包含业务正文或凭据的异常消息写入评估结果。
        error_category = f"workflow_exception:{type(exc).__name__}"
        summary = _exception_summary(scenario, repositories, error_category)
        return _evaluate_summary(
            scenario,
            expected,
            summary,
            execution_error=error_category,
        )


def run_product_launch_suite(
    root: Path = DEFAULT_EVAL_ROOT,
) -> list[EvaluationResult]:
    return [
        run_product_launch_scenario(
            load_product_launch_scenario(scenario_path),
            load_product_launch_expectation(expected_path),
        )
        for scenario_path, expected_path in discover_product_launch_fixture_pairs(root)
    ]


def assert_product_launch_regression_gate(
    results: Sequence[EvaluationResult],
) -> None:
    failures: list[str] = []
    for result in results:
        reasons = []
        if result.status != "passed":
            reasons.append("result_status")
        if result.score < 1.0:
            reasons.append("result_score")
        if result.threshold != 1.0:
            reasons.append("result_threshold")
        if any(
            not metric.passed or metric.score < 1.0 or metric.threshold != 1.0
            for metric in result.metrics
        ):
            reasons.append("metric")
        if reasons:
            failures.append(f"{result.scenario_id}:{','.join(reasons)}")
    if failures:
        raise EvaluationGateError(
            f"Product Launch regression gate failed: {'; '.join(failures)}"
        )
