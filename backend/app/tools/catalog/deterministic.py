from app.adapters.mock_marketplaces import get_mock_adapter
from app.domain.schemas import ListingDraft
from app.services.profit import ProfitInput, estimate_profit
from app.services.suppliers import SupplierInput, score_supplier
from app.tools.catalog.base import ToolHandlerCatalog
from app.tools.schemas import ToolExecutionContext


async def estimate_profit_handler(
    input_data: ProfitInput,
    context: ToolExecutionContext,
):
    return estimate_profit(input_data)


async def score_supplier_handler(
    input_data: SupplierInput,
    context: ToolExecutionContext,
):
    return score_supplier(input_data)


async def validate_listing_handler(
    input_data: ListingDraft,
    context: ToolExecutionContext,
):
    return get_mock_adapter(input_data.marketplace).validate_listing(input_data)


def build_default_handler_catalog() -> ToolHandlerCatalog:
    catalog = ToolHandlerCatalog()
    catalog.register("estimate_profit", estimate_profit_handler)
    catalog.register("score_supplier", score_supplier_handler)
    catalog.register("validate_listing", validate_listing_handler)
    return catalog
