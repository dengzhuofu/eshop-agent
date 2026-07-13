import hashlib
import json
from typing import Any

from app.domain.enums import Marketplace
from app.domain.schemas import ListingDraft, ListingVersion


def content_hash_for_draft(draft: ListingDraft) -> str:
    payload = draft.model_dump(mode="json")
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def create_listing_version(
    *,
    workflow_id: str,
    tenant_id: str,
    draft: ListingDraft,
    stage: str,
    created_by_agent: str,
    created_step: str,
    version_number: int,
    source_version_id: str | None = None,
    changes: list[str] | None = None,
    risk_flags: list[dict[str, Any]] | None = None,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    content_hash = content_hash_for_draft(draft)
    version = ListingVersion(
        version_id=listing_version_id(workflow_id, draft.marketplace, version_number, content_hash),
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        marketplace=draft.marketplace,
        sku=draft.sku,
        locale=draft.locale,
        source_version_id=source_version_id,
        version_number=version_number,
        stage=stage,
        draft=draft,
        changes=changes or [],
        risk_flags=risk_flags or [],
        validation=validation,
        created_by_agent=created_by_agent,
        created_step=created_step,
        content_hash=content_hash,
    )
    return version.model_dump(mode="json")


def listing_version_summary(version: dict[str, Any]) -> dict[str, Any]:
    draft = version.get("draft", {})
    validation = version.get("validation") or {}
    return {
        "version_id": version["version_id"],
        "marketplace": version["marketplace"],
        "sku": version["sku"],
        "locale": version["locale"],
        "source_version_id": version.get("source_version_id"),
        "version_number": version["version_number"],
        "stage": version["stage"],
        "content_hash": version["content_hash"],
        "title": draft.get("title"),
        "price": draft.get("price"),
        "changes": version.get("changes", []),
        "risk_flag_count": len(version.get("risk_flags", [])),
        "validation_valid": validation.get("valid"),
    }


def listing_version_id(
    workflow_id: str,
    marketplace: Marketplace,
    version_number: int,
    content_hash: str,
) -> str:
    return f"lv_{workflow_id}_{marketplace.value}_{version_number}_{content_hash[:10]}"
