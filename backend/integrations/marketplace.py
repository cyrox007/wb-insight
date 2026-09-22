from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from models.sync_job_model import SyncJob
from models.tokens_model import APIToken, Marketplace


class MarketplaceAdapter(ABC):
    """Граница синхронизации конкретного маркетплейса для общего оркестратора."""

    marketplace: Marketplace

    @abstractmethod
    async def sync_entity(
        self,
        session: AsyncSession,
        job: SyncJob,
        token: APIToken,
    ) -> None:
        """Синхронизирует одну каноническую сущность одного кабинета маркетплейса."""
        raise NotImplementedError


class MarketplaceAdapterNotFoundError(ValueError):
    def __init__(self, marketplace: Marketplace) -> None:
        super().__init__(f"Адаптер маркетплейса не настроен: {marketplace.value}")
        self.marketplace = marketplace
