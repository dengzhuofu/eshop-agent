from pydantic import BaseModel

from app.domain.enums import AgentRole


class PromptTemplateMetadata(BaseModel):
    name: str
    version: str
    owner_agent: AgentRole
    purpose: str
    required_context_keys: set[str]
    forbidden_context_keys: set[str]


def get_prompt_templates() -> dict[str, PromptTemplateMetadata]:
    templates = [
        PromptTemplateMetadata(
            name="listing_agent_system",
            version="0.1.0",
            owner_agent=AgentRole.LISTING,
            purpose="Generate marketplace-specific listing drafts within platform policy boundaries.",
            required_context_keys={"product_facts", "marketplace_rules", "locale"},
            forbidden_context_keys={"raw_secret", "customer_pii", "payment_data"},
        ),
        PromptTemplateMetadata(
            name="customer_support_agent_system",
            version="0.1.0",
            owner_agent=AgentRole.CUSTOMER_SUPPORT,
            purpose="Draft grounded support responses using order tools and RAG citations.",
            required_context_keys={"ticket", "order_summary", "policy_citations"},
            forbidden_context_keys={"secret", "raw_secret", "full_payment_credentials"},
        ),
        PromptTemplateMetadata(
            name="risk_review_agent_system",
            version="0.1.0",
            owner_agent=AgentRole.RISK_REVIEW,
            purpose="Assess unsafe claims, low-margin launches, approval needs, and evidence gaps.",
            required_context_keys={"risk_inputs", "validation_results"},
            forbidden_context_keys={"raw_secret", "full_payment_credentials"},
        ),
    ]
    return {template.name: template for template in templates}

