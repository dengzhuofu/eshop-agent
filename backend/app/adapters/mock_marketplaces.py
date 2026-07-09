import hashlib

from app.adapters.base import MarketplaceAdapter
from app.domain.enums import Marketplace, RiskLevel
from app.domain.schemas import ListingDraft, PublishResult, ValidationIssue, ValidationResult

UNSUPPORTED_CLAIM_TERMS = ("guarantee", "guaranteed", "perfect results", "cure", "medical")


class BaseMockMarketplaceAdapter:
    marketplace: Marketplace
    name: str

    def publish_listing(self, draft: ListingDraft, idempotency_key: str) -> PublishResult:
        validation = self.validate_listing(draft)
        if not validation.valid:
            issue_fields = ", ".join(issue.field for issue in validation.issues)
            raise ValueError(f"Cannot publish invalid listing: {issue_fields}")

        digest = hashlib.sha1(
            f"{self.marketplace.value}:{draft.sku}:{idempotency_key}".encode("utf-8")
        ).hexdigest()[:10]
        return PublishResult(
            listing_id=f"{self.marketplace.value.upper()}-{digest}",
            status="published",
            marketplace=self.marketplace,
            idempotency_key=idempotency_key,
        )

    def _common_issues(self, draft: ListingDraft) -> list[ValidationIssue]:
        issues: list[ValidationIssue] = []
        if not draft.attributes.get("category"):
            issues.append(
                ValidationIssue(
                    field="attributes.category",
                    message="Category is required.",
                    risk_level=RiskLevel.HIGH,
                )
            )
        return issues

    def _unsupported_claim_issues(self, draft: ListingDraft) -> list[ValidationIssue]:
        text = f"{draft.title} {draft.description} {' '.join(draft.bullet_points)}".lower()
        if any(term in text for term in UNSUPPORTED_CLAIM_TERMS):
            return [
                ValidationIssue(
                    field="claims",
                    message="Unsupported marketing or compliance claim detected.",
                    risk_level=RiskLevel.HIGH,
                )
            ]
        return []


class MockAmazonAdapter(BaseMockMarketplaceAdapter):
    marketplace = Marketplace.AMAZON
    name = "Mock Amazon"

    def validate_listing(self, draft: ListingDraft) -> ValidationResult:
        issues = self._common_issues(draft)
        if len(draft.title) > 200:
            issues.append(
                ValidationIssue(
                    field="title",
                    message="Amazon-like title must be 200 characters or less.",
                    risk_level=RiskLevel.MEDIUM,
                )
            )
        if len(draft.bullet_points) < 3:
            issues.append(
                ValidationIssue(
                    field="bullet_points",
                    message="Amazon-like listings require at least three bullet points.",
                    risk_level=RiskLevel.MEDIUM,
                )
            )
        issues.extend(self._unsupported_claim_issues(draft))
        return ValidationResult(valid=not issues, issues=issues)


class MockShopifyAdapter(BaseMockMarketplaceAdapter):
    marketplace = Marketplace.SHOPIFY
    name = "Mock Shopify"

    def validate_listing(self, draft: ListingDraft) -> ValidationResult:
        issues = self._common_issues(draft)
        if len(draft.title) > 255:
            issues.append(
                ValidationIssue(
                    field="title",
                    message="Shopify-like title must be 255 characters or less.",
                    risk_level=RiskLevel.MEDIUM,
                )
            )
        return ValidationResult(valid=not issues, issues=issues)


class MockTikTokShopAdapter(BaseMockMarketplaceAdapter):
    marketplace = Marketplace.TIKTOK_SHOP
    name = "Mock TikTok Shop"

    def validate_listing(self, draft: ListingDraft) -> ValidationResult:
        issues = self._common_issues(draft)
        if len(draft.title) > 120:
            issues.append(
                ValidationIssue(
                    field="title",
                    message="TikTok Shop-like title must be 120 characters or less.",
                    risk_level=RiskLevel.MEDIUM,
                )
            )
        if not draft.attributes.get("video_hook"):
            issues.append(
                ValidationIssue(
                    field="attributes.video_hook",
                    message="TikTok Shop-like listings require a short video hook.",
                    risk_level=RiskLevel.LOW,
                )
            )
        issues.extend(self._unsupported_claim_issues(draft))
        return ValidationResult(valid=not issues, issues=issues)


def get_mock_adapter(marketplace: Marketplace) -> MarketplaceAdapter:
    adapters: dict[Marketplace, MarketplaceAdapter] = {
        Marketplace.AMAZON: MockAmazonAdapter(),
        Marketplace.SHOPIFY: MockShopifyAdapter(),
        Marketplace.TIKTOK_SHOP: MockTikTokShopAdapter(),
    }
    try:
        return adapters[marketplace]
    except KeyError as exc:
        raise ValueError(f"Unsupported marketplace: {marketplace}") from exc
