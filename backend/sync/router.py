from sqlalchemy.ext.asyncio import AsyncSession

from integrations.registry import get_marketplace_adapter
from integrations.wildberries.adapter import WildberriesAdapter
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken


# Временный совместимый контракт для существующих тестов WB и внутренних импортов.
# Источник истины по обработчикам находится в WildberriesAdapter.handlers.
HANDLERS = WildberriesAdapter.handlers


async def call_marketplace_api(
    session: AsyncSession,
    job: SyncJob,
    token: APIToken,
) -> None:
    """Передаёт задачу синхронизации адаптеру маркетплейса указанного кабинета."""
    adapter = get_marketplace_adapter(token.marketplace)
    await adapter.sync_entity(session, job, token)


async def call_wb_api(
    session: AsyncSession,
    job: SyncJob,
    token: APIToken,
) -> None:
    """Совместимая оболочка для worker и тестов на период миграции оркестрации."""
    await call_marketplace_api(session=session, job=job, token=token)