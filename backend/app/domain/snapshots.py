from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkflowSnapshot(BaseModel):
    id: str = Field(min_length=1)
    workflow_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    checkpoint_name: str = Field(min_length=1)
    version: int = Field(ge=1)
    state: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
