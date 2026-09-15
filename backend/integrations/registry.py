from integrations.marketplace import (
    MarketplaceAdapter,
    MarketplaceAdapterNotFoundError,
)
from integrations.wildberries.adapter import WildberriesAdapter
from models.tokens_model import Marketplace


_ADAPTERS: dict[Marketplace, MarketplaceAdapter] = {
    Marketplace.WILDBERRIES: WildberriesAdapter(),
}


def get_marketplace_adapter(marketplace: Marketplace) -> MarketplaceAdapter:
    try:
        return _ADAPTERS[marketplace]
    except KeyError as exc:
        raise MarketplaceAdapterNotFoundError(marketplace) from exc
