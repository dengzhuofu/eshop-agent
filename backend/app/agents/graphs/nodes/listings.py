from typing import Any

from app.adapters.mock_marketplaces import get_mock_adapter
from app.agents.profiles import list_agent_profiles
from app.agents.graphs.state import CommerceAgentState
from app.domain.enums import AgentRole, ApprovalStatus, Marketplace, RiskLevel, WorkflowState
from app.domain.schemas import ListingApprovalIndex, ListingDraft, ListingVersion
from app.repositories.approvals import get_approval_repository
from app.security.boundary import AgentBoundaryPolicy, ToolAccessContext
from app.services.listing_versions import (
    content_hash_for_draft,
    create_listing_version,
    listing_version_id,
    listing_version_summary,
)
from app.tools.registry import build_default_registry


def _append_step(state: CommerceAgentState, step: str) -> list[str]:
    return [*state["completed_steps"], step]


def _draft_for_marketplace(marketplace: Marketplace, state: CommerceAgentState) -> ListingDraft:
    attributes: dict[str, str | int | float | bool] = {"category": "home_storage"}
    if marketplace == Marketplace.SHOPIFY:
        attributes["seo_title"] = "Under-bed organizer"
    if marketplace == Marketplace.TIKTOK_SHOP:
        attributes["video_hook"] = "Transform your room"

    return ListingDraft(
        marketplace=marketplace,
        sku=f"SKU-{marketplace.value.upper()}-001",
        title="Foldable under-bed storage organizer",
        description=f"Launch preview for {state['product_idea']}.",
        bullet_points=["Fits under beds", "Foldable fabric body", "Easy seasonal storage"],
        price=state["target_price"],
        attributes=attributes,
    )


def _localized_draft(
    draft: ListingDraft,
    locale: str,
    risk_preference: str,
) -> tuple[ListingDraft, list[str], list[dict[str, Any]]]:
    attributes = dict(draft.attributes)
    changes = ["locale"]
    risk_flags: list[dict[str, Any]] = []
    title = draft.title
    description = draft.description
    bullet_points = [*draft.bullet_points]

    if locale == "en-GB":
        attributes["unit_style"] = "metric"
        attributes["market_wording"] = "UK English"
        changes.extend(["unit_style", "market_wording"])
    elif locale == "en-US":
        attributes["unit_style"] = "imperial"
        attributes["market_wording"] = "US English"
        changes.extend(["unit_style", "market_wording"])
    else:
        attributes["market_wording"] = "international English"
        changes.append("market_wording")

    if risk_preference == "localization_risk":
        description = f"{description} Guaranteed perfect results for every home."
        changes.append("claim_review")
        risk_flags.append(
            {
                "marketplace": draft.marketplace.value,
                "locale": locale,
                "field": "description",
                "message": "Localized copy contains an unsupported guaranteed-results claim.",
                "risk_level": RiskLevel.HIGH.value,
            }
        )

    return (
        draft.model_copy(
            update={
                "title": title,
                "description": description,
                "bullet_points": bullet_points,
                "attributes": attributes,
                "locale": locale,
            }
        ),
        changes,
        risk_flags,
    )


def _selected_listing_versions(state: CommerceAgentState) -> list[dict[str, Any]]:
    version_lookup = {version["version_id"]: version for version in state.get("listing_versions", [])}
    return [
        version_lookup[version_id]
        for version_id in state.get("selected_listing_version_ids", [])
        if version_id in version_lookup
    ]


def _versions_with_validation(
    listing_versions: list[dict[str, Any]],
    validation_by_version_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    updated_versions = []
    for version in listing_versions:
        validation = validation_by_version_id.get(version["version_id"])
        if validation is None:
            updated_versions.append(version)
            continue
        updated_versions.append({**version, "stage": "validated", "validation": validation})
    return updated_versions


def _versions_with_stage(
    listing_versions: list[dict[str, Any]],
    version_ids: set[str],
    stage: str,
) -> list[dict[str, Any]]:
    return [
        {**version, "stage": stage} if version["version_id"] in version_ids else version
        for version in listing_versions
    ]


def localization_node(state: CommerceAgentState) -> dict:
    locale = state["target_locale"]
    listing_drafts = [
        _draft_for_marketplace(Marketplace(marketplace_value), state)
        for marketplace_value in state["target_marketplaces"]
    ]
    listing_versions = []
    localized_listings = []
    localization_risk_flags = []
    selected_listing_version_ids = []
    tool_calls = [*state["tool_calls"]]

    for draft in listing_drafts:
        base_version = create_listing_version(
            workflow_id=state["workflow_id"],
            tenant_id=state["tenant_id"],
            draft=draft,
            stage="draft",
            created_by_agent=AgentRole.LISTING.value,
            created_step="localization",
            version_number=1,
            changes=["initial_draft"],
        )
        localized_draft, changes, risk_flags = _localized_draft(
            draft,
            locale,
            state["risk_preference"],
        )
        localized_version = create_listing_version(
            workflow_id=state["workflow_id"],
            tenant_id=state["tenant_id"],
            draft=localized_draft,
            stage="localized",
            created_by_agent=AgentRole.LOCALIZATION.value,
            created_step="localization",
            version_number=2,
            source_version_id=base_version["version_id"],
            changes=changes,
            risk_flags=risk_flags,
        )
        listing_versions.extend([base_version, localized_version])
        localization_risk_flags.extend(risk_flags)
        selected_listing_version_ids.append(localized_version["version_id"])
        localized_listings.append(
            {
                "marketplace": draft.marketplace.value,
                "source_sku": draft.sku,
                "locale": locale,
                "changes": changes,
                "risk_flags": risk_flags,
                "listing_version_id": localized_version["version_id"],
                "listing_content_hash": localized_version["content_hash"],
                "draft": localized_draft.model_dump(mode="json"),
            }
        )
        tool_calls.append(
            {
                "tool": "localize_listing",
                "agent_role": AgentRole.LOCALIZATION.value,
                "marketplace": draft.marketplace.value,
                "locale": locale,
                "listing_version_id": localized_version["version_id"],
                "listing_content_hash": localized_version["content_hash"],
                "risk_level": RiskLevel.MEDIUM.value,
                "status": "completed",
            }
        )

    return {
        "current_agent": AgentRole.LOCALIZATION,
        "current_step": WorkflowState.LOCALIZING,
        "completed_steps": _append_step(state, "localization"),
        "listing_drafts": [draft.model_dump(mode="json") for draft in listing_drafts],
        "localized_listings": localized_listings,
        "listing_versions": listing_versions,
        "selected_listing_version_ids": selected_listing_version_ids,
        "localization_risk_flags": localization_risk_flags,
        "tool_calls": tool_calls,
        "evidence": [
            *state["evidence"],
            {
                "source": "mock_localization_rules",
                "summary": f"Localized {len(localized_listings)} listing drafts for {locale}.",
                "confidence": 0.84,
            },
        ],
    }


def listing_validation_node(state: CommerceAgentState) -> dict:
    validations = []
    validation_by_version_id = {}
    tool_calls = [*state["tool_calls"]]

    for version in _selected_listing_versions(state):
        draft = ListingDraft.model_validate(version["draft"])
        marketplace = draft.marketplace
        adapter = get_mock_adapter(marketplace)
        validation = adapter.validate_listing(draft)
        validation_payload = {
            "marketplace": marketplace.value,
            "listing_version_id": version["version_id"],
            "listing_content_hash": version["content_hash"],
            "valid": validation.valid,
            "issues": [issue.model_dump(mode="json") for issue in validation.issues],
        }
        validations.append(validation_payload)
        validation_by_version_id[version["version_id"]] = validation_payload
        tool_calls.append(
            {
                "tool": "validate_listing",
                "agent_role": AgentRole.LISTING.value,
                "marketplace": marketplace.value,
                "listing_version_id": version["version_id"],
                "listing_content_hash": version["content_hash"],
                "risk_level": RiskLevel.LOW.value,
                "status": "completed",
            }
        )

    return {
        "current_agent": AgentRole.LISTING,
        "current_step": WorkflowState.DRAFTING_LISTINGS,
        "completed_steps": _append_step(state, "listing_validation"),
        "listing_versions": _versions_with_validation(state["listing_versions"], validation_by_version_id),
        "listing_validations": validations,
        "tool_calls": tool_calls,
    }


def await_approval_node(state: CommerceAgentState) -> dict:
    approval_id = f"appr_{state['workflow_id']}"
    selected_versions = _selected_listing_versions(state)
    listing_version_ids = [version["version_id"] for version in selected_versions]
    approval = get_approval_repository().upsert_pending(
        approval_id=approval_id,
        workflow_id=state["workflow_id"],
        tenant_id=state["tenant_id"],
        requested_by=AgentRole.SUPERVISOR.value,
        reason_codes=state["approval_reasons"],
        risk_level=state["risk_level"],
        resource_type="workflow",
        resource_id=state["workflow_id"],
        metadata={
            "tool": "publish_listing",
            "product_idea": state["product_idea"],
            "target_marketplaces": state["target_marketplaces"],
            "target_price": state["target_price"],
            "listing_version_ids": listing_version_ids,
            "listing_version_hashes": {
                version["version_id"]: version["content_hash"] for version in selected_versions
            },
            "listing_version_summary": [
                listing_version_summary(version) for version in selected_versions
            ],
            "publish_diff_summary": [
                {
                    "version_id": version["version_id"],
                    "marketplace": version["marketplace"],
                    "locale": version["locale"],
                    "source_version_id": version.get("source_version_id"),
                    "changes": version.get("changes", []),
                }
                for version in selected_versions
            ],
        },
    )
    return {
        "current_agent": AgentRole.SUPERVISOR,
        "current_step": WorkflowState.AWAITING_APPROVAL,
        "completed_steps": _append_step(state, "await_approval"),
        "approval_request_id": approval.id,
        "approval_request": approval.model_dump(mode="json"),
    }


def publish_listing_node(state: CommerceAgentState) -> dict:
    approval = get_approval_repository().get(state["approval_request_id"])
    if approval is None:
        return _failed_publish_state(state, "approval request not found")

    if approval.status != ApprovalStatus.APPROVED:
        return _failed_publish_state(
            state,
            "approval is not approved",
            approval_request=approval.model_dump(mode="json"),
        )

    if (
        state.get("workflow_id") != approval.workflow_id
        or state.get("tenant_id") != approval.tenant_id
    ):
        return _failed_publish_state(
            state,
            "approval and workflow state ownership mismatch",
            approval_request=approval.model_dump(mode="json"),
        )

    if not state["target_marketplaces"] or state["target_price"] <= 0:
        return _failed_publish_state(
            state,
            "approval metadata is incomplete",
            approval_request=approval.model_dump(mode="json"),
        )

    publish_versions, version_error = _approval_bound_versions(
        state,
        approval.metadata,
        workflow_id=approval.workflow_id,
        tenant_id=approval.tenant_id,
    )
    if version_error is not None:
        return _failed_publish_state(
            state,
            version_error,
            approval_request=approval.model_dump(mode="json"),
        )
    approved_version_ids = [version["version_id"] for version in publish_versions]

    boundary = AgentBoundaryPolicy(
        profiles=list_agent_profiles(),
        registry=build_default_registry(),
    )
    decision = boundary.evaluate_tool_access(
        ToolAccessContext(
            agent_role=AgentRole.SUPERVISOR,
            tool_name="publish_listing",
            actor_tenant_id=approval.tenant_id,
            target_tenant_id=approval.tenant_id,
            actor_permissions={"listing:publish"},
            approved=True,
            payload={"approval_request_id": approval.id},
        )
    )
    if not decision.allowed:
        return _failed_publish_state(
            state,
            decision.reasons,
            approval_request=approval.model_dump(mode="json"),
            approved_listing_version_ids=approved_version_ids,
        )

    publish_results = []
    published_version_ids = []
    tool_calls = [*state["tool_calls"]]
    for version in publish_versions:
        draft = ListingDraft.model_validate(version["draft"])
        marketplace = draft.marketplace
        adapter = get_mock_adapter(marketplace)
        idempotency_key = f"{approval.id}:{version['version_id']}:{marketplace.value}"
        try:
            result = adapter.publish_listing(
                draft,
                idempotency_key=idempotency_key,
            )
        except ValueError as exc:
            tool_calls.append(
                {
                    "tool": "publish_listing",
                    "agent_role": AgentRole.SUPERVISOR.value,
                    "marketplace": marketplace.value,
                    "listing_version_id": version["version_id"],
                    "listing_content_hash": version["content_hash"],
                    "risk_level": RiskLevel.HIGH.value,
                    "status": "failed",
                    "approval_request_id": approval.id,
                    "idempotency_key": idempotency_key,
                    "error": str(exc),
                }
            )
            failed_versions = _versions_with_stage(
                state["listing_versions"],
                set(published_version_ids),
                "published",
            )
            failed_versions = _versions_with_stage(
                failed_versions,
                {version["version_id"]},
                "publish_failed",
            )
            return _failed_publish_state(
                state,
                str(exc),
                approval_request=approval.model_dump(mode="json"),
                publish_results=publish_results,
                tool_calls=tool_calls,
                listing_versions=failed_versions,
                approved_listing_version_ids=approved_version_ids,
            )

        result_payload = result.model_dump(mode="json")
        result_payload.update(
            {
                "listing_version_id": version["version_id"],
                "listing_content_hash": version["content_hash"],
            }
        )
        publish_results.append(result_payload)
        published_version_ids.append(version["version_id"])
        tool_calls.append(
            {
                "tool": "publish_listing",
                "agent_role": AgentRole.SUPERVISOR.value,
                "marketplace": marketplace.value,
                "listing_version_id": version["version_id"],
                "listing_content_hash": version["content_hash"],
                "risk_level": RiskLevel.HIGH.value,
                "status": "completed",
                "approval_request_id": approval.id,
                "idempotency_key": idempotency_key,
            }
        )

    return {
        "current_agent": AgentRole.SUPERVISOR,
        "current_step": WorkflowState.COMPLETED,
        "completed_steps": _append_step(state, "publish_listing"),
        "approval_request": approval.model_dump(mode="json"),
        "listing_versions": _versions_with_stage(
            state["listing_versions"],
            set(approved_version_ids),
            "published",
        ),
        "approved_listing_version_ids": approved_version_ids,
        "publish_results": publish_results,
        "tool_calls": tool_calls,
    }


def _approval_bound_versions(
    state: CommerceAgentState,
    approval_metadata: dict[str, Any],
    *,
    workflow_id: str,
    tenant_id: str,
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        approval_index = ListingApprovalIndex.model_validate(approval_metadata)
    except (TypeError, ValueError):
        return [], "approval listing version index is invalid"
    approved_ids = approval_index.listing_version_ids
    approved_hashes = approval_index.listing_version_hashes
    selected_ids = state.get("selected_listing_version_ids", [])
    if not isinstance(selected_ids, list) or not all(
        isinstance(version_id, str) for version_id in selected_ids
    ):
        return [], "selected listing version index is invalid"
    if len(selected_ids) != len(set(selected_ids)):
        return [], "selected listing versions contain duplicates"
    if len(approved_ids) != len(set(approved_ids)):
        return [], "approval listing versions contain duplicates"
    # 审批集合必须与快照选择完全一致，不能静默少发、换序或夹带其他版本。
    if approved_ids != selected_ids:
        return [], "approval listing versions do not match selected versions"

    version_lookup = {
        version.get("version_id"): version
        for version in state["listing_versions"]
        if isinstance(version, dict) and isinstance(version.get("version_id"), str)
    }
    publish_versions = []
    for version_id in approved_ids:
        version = version_lookup.get(version_id)
        if version is None:
            return [], "approved listing version not found"
        try:
            parsed_version = ListingVersion.model_validate(version)
        except (TypeError, ValueError):
            return [], "approved listing version is invalid"
        if (
            parsed_version.workflow_id != workflow_id
            or parsed_version.tenant_id != tenant_id
        ):
            return [], "approved listing version ownership mismatch"
        draft = parsed_version.draft
        # 审批只保存轻量索引；发布前重算正文哈希，避免版本记录与草稿被分别篡改。
        if content_hash_for_draft(draft) != parsed_version.content_hash:
            return [], "listing version content hash mismatch"
        expected_version_id = listing_version_id(
            workflow_id,
            draft.marketplace,
            parsed_version.version_number,
            parsed_version.content_hash,
        )
        if expected_version_id != version_id:
            return [], "listing version id mismatch"
        if approved_hashes.get(version_id) != parsed_version.content_hash:
            return [], "approved listing version hash mismatch"
        publish_versions.append(parsed_version.model_dump(mode="json"))
    return publish_versions, None


def _failed_publish_state(
    state: CommerceAgentState,
    errors: str | list[str],
    *,
    approval_request: dict[str, Any] | None = None,
    publish_results: list[dict[str, Any]] | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    listing_versions: list[dict[str, Any]] | None = None,
    approved_listing_version_ids: list[str] | None = None,
) -> dict:
    error_list = [errors] if isinstance(errors, str) else errors
    failed_state = {
        "current_agent": AgentRole.SUPERVISOR,
        "current_step": WorkflowState.FAILED,
        "completed_steps": _append_step(state, "publish_listing"),
        "errors": [*state["errors"], *error_list],
        "publish_results": publish_results if publish_results is not None else [],
    }
    if approval_request is not None:
        failed_state["approval_request"] = approval_request
    if tool_calls is not None:
        failed_state["tool_calls"] = tool_calls
    if listing_versions is not None:
        failed_state["listing_versions"] = listing_versions
    if approved_listing_version_ids is not None:
        failed_state["approved_listing_version_ids"] = approved_listing_version_ids
    return failed_state
