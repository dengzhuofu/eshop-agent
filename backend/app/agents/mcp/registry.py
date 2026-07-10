from pydantic import BaseModel


class MCPConnectorMetadata(BaseModel):
    name: str
    purpose: str
    enabled_by_default: bool
    secret_env_vars: set[str]


def list_mcp_connectors() -> list[MCPConnectorMetadata]:
    return [
        MCPConnectorMetadata(
            name="marketplace_api",
            purpose="Future connector facade for real marketplace APIs.",
            enabled_by_default=False,
            secret_env_vars={"MARKETPLACE_API_TOKEN"},
        ),
        MCPConnectorMetadata(
            name="support_knowledge_base",
            purpose="Future connector facade for support policy and FAQ retrieval.",
            enabled_by_default=False,
            secret_env_vars={"SUPPORT_KB_API_TOKEN"},
        ),
    ]

