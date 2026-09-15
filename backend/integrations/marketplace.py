from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from models.sync_job_model import SyncJob
from models.tokens_model import APIToken, Marketplace


class MarketplaceAdapter(ABC):
    """Marketplace-specific sync boundary used by the generic orchestration layer."""

    marketplace: Marketplace

    @abstractmethod
    async def sync_entity(
        self,
        session: AsyncSession,
        job: SyncJob,
        token: APIToken,
    ) -> None:
        """Synchronize one canonical entity for exactly one marketplace account."""
        raise NotImplementedError


class MarketplaceAdapterNotFoundError(ValueError):
    def __init__(self, marketplace: Marketplace) -> None:
        super().__init__(f"Marketplace adapter is not configured: {marketplace.value}")
        self.marketplace = marketplace
