from pydantic import BaseModel

from app.domain.enums import AgentRole


class AgentSkillMetadata(BaseModel):
    name: str
    purpose: str
    allowed_agents: set[AgentRole]


def list_agent_skills() -> list[AgentSkillMetadata]:
    return [
        AgentSkillMetadata(
            name="cross_border_listing_policy",
            purpose="Marketplace listing safety, localization, and unsupported claim guidance.",
            allowed_agents={AgentRole.LISTING, AgentRole.LOCALIZATION, AgentRole.RISK_REVIEW},
        ),
        AgentSkillMetadata(
            name="customer_support_rag_policy",
            purpose="Customer support RAG boundaries for policy-grounded responses.",
            allowed_agents={AgentRole.CUSTOMER_SUPPORT},
        ),
        AgentSkillMetadata(
            name="commerce_profit_review",
            purpose="Profit and launch-risk interpretation guidance.",
            allowed_agents={AgentRole.PROFIT_ANALYST, AgentRole.RISK_REVIEW},
        ),
    ]

