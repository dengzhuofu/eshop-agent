from enum import StrEnum

from pydantic import BaseModel


class MemoryScope(StrEnum):
    WORKFLOW = "workflow"
    TENANT = "tenant"
    GLOBAL = "global"


class MemoryPolicy(BaseModel):
    name: str
    scope: MemoryScope
    purpose: str
    allow_cross_tenant_read: bool
    forbidden_data_classes: set[str]
    retention_days: int


def get_memory_policies() -> list[MemoryPolicy]:
    return [
        MemoryPolicy(
            name="workflow_ephemeral_memory",
            scope=MemoryScope.WORKFLOW,
            purpose="Short-lived state for a single product launch workflow.",
            allow_cross_tenant_read=False,
            forbidden_data_classes={"raw_secret", "full_payment_credentials"},
            retention_days=14,
        ),
        MemoryPolicy(
            name="tenant_workflow_memory",
            scope=MemoryScope.TENANT,
            purpose="Tenant-scoped historical workflow lessons and reusable business preferences.",
            allow_cross_tenant_read=False,
            forbidden_data_classes={"raw_secret", "full_payment_credentials", "payment_data"},
            retention_days=180,
        ),
        MemoryPolicy(
            name="global_playbook_memory",
            scope=MemoryScope.GLOBAL,
            purpose="Non-sensitive general playbooks and product development conventions.",
            allow_cross_tenant_read=True,
            forbidden_data_classes={"raw_secret", "tenant_data", "customer_pii", "payment_data"},
            retention_days=365,
        ),
    ]
