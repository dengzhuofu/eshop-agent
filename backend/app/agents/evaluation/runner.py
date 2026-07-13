import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.agents.evaluation.results import (
    ProductLaunchEvaluationSummary,
    Sha256Hash,
    canonical_summary_hash,
)
from app.domain.enums import Marketplace

DEFAULT_EVAL_ROOT = Path(__file__).resolve().parents[3] / "evals" / "product_launch"


class EvaluationFixtureError(ValueError):
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
