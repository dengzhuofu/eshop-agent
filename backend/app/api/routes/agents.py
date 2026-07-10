from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.agents.profiles import list_agent_profiles
from app.domain.enums import AgentRole
from app.security.boundary import AgentBoundaryPolicy, ToolAccessContext
from app.tools.registry import build_default_registry

router = APIRouter(prefix="/agents", tags=["agents"])


class AccessCheckRequest(BaseModel):
    agent_role: AgentRole
    tool_name: str
    actor_tenant_id: str = Field(min_length=1)
    target_tenant_id: str = Field(min_length=1)
    actor_permissions: set[str]
    approved: bool = False
    payload: dict = Field(default_factory=dict)


@router.get("/profiles")
def get_agent_profiles() -> dict:
    return {
        "profiles": [
            profile.model_dump(mode="json")
            for profile in list_agent_profiles()
        ]
    }


@router.post("/access-check")
def check_agent_access(request: AccessCheckRequest) -> dict:
    policy = AgentBoundaryPolicy(
        profiles=list_agent_profiles(),
        registry=build_default_registry(),
    )
    decision = policy.evaluate_tool_access(
        ToolAccessContext(
            agent_role=request.agent_role,
            tool_name=request.tool_name,
            actor_tenant_id=request.actor_tenant_id,
            target_tenant_id=request.target_tenant_id,
            actor_permissions=request.actor_permissions,
            approved=request.approved,
            payload=request.payload,
        )
    )
    return decision.model_dump(mode="json")

