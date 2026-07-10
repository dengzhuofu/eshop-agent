from pydantic import BaseModel

from app.domain.enums import AgentRole


class EvaluationScenario(BaseModel):
    name: str
    owner_agent: AgentRole
    purpose: str
    requires_citations: bool
    required_metrics: set[str]


def list_evaluation_scenarios() -> list[EvaluationScenario]:
    return [
        EvaluationScenario(
            name="listing_claim_safety",
            owner_agent=AgentRole.LISTING,
            purpose="Detect unsupported claims and platform policy conflicts in listing drafts.",
            requires_citations=False,
            required_metrics={"claim_safety", "required_field_completeness"},
        ),
        EvaluationScenario(
            name="support_rag_groundedness",
            owner_agent=AgentRole.CUSTOMER_SUPPORT,
            purpose="Check that support responses are grounded in order facts and policy citations.",
            requires_citations=True,
            required_metrics={"groundedness", "policy_match", "tone_safety"},
        ),
        EvaluationScenario(
            name="workflow_approval_correctness",
            owner_agent=AgentRole.SUPERVISOR,
            purpose="Check that high-risk workflow actions pause for approval.",
            requires_citations=False,
            required_metrics={"approval_recall", "unsafe_action_block_rate"},
        ),
    ]

