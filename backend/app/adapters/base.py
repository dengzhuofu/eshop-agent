from typing import Protocol

from app.domain.schemas import ListingDraft, PublishResult, ValidationResult


class MarketplaceAdapter(Protocol):
    name: str

    def validate_listing(self, draft: ListingDraft) -> ValidationResult:
        """Validate a listing draft against marketplace-specific rules."""

    def publish_listing(self, draft: ListingDraft, idempotency_key: str) -> PublishResult:
        """Publish a listing draft through the adapter."""

