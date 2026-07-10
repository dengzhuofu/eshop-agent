from enum import StrEnum

from pydantic import BaseModel


class CheckpointKind(StrEnum):
    SNAPSHOT = "snapshot"
    HUMAN_APPROVAL = "human_approval"
    RETRYABLE_FAILURE = "retryable_failure"


class CheckpointPolicy(BaseModel):
    name: str
    kind: CheckpointKind
    after_node: str
    interrupts_graph: bool
    retention_days: int


def get_checkpoint_policies() -> list[CheckpointPolicy]:
    return [
        CheckpointPolicy(
            name="after_read_only_research",
            kind=CheckpointKind.SNAPSHOT,
            after_node="product_research",
            interrupts_graph=False,
            retention_days=30,
        ),
        CheckpointPolicy(
            name="before_publish_listing",
            kind=CheckpointKind.HUMAN_APPROVAL,
            after_node="risk_review",
            interrupts_graph=True,
            retention_days=90,
        ),
        CheckpointPolicy(
            name="after_retryable_tool_failure",
            kind=CheckpointKind.RETRYABLE_FAILURE,
            after_node="tool_execution",
            interrupts_graph=False,
            retention_days=14,
        ),
    ]

