from sqlalchemy.ext.asyncio import AsyncSession

from integrations.registry import get_marketplace_adapter
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken


async def call_marketplace_api(
    session: AsyncSession,
    job: SyncJob,
    token: APIToken,
) -> None:
    """Dispatch a sync job to the adapter for the job's marketplace account."""
    adapter = get_marketplace_adapter(token.marketplace)
    await adapter.sync_entity(session, job, token)


async def call_wb_api(
    session: AsyncSession,
    job: SyncJob,
    token: APIToken,
) -> None:
    """Compatibility wrapper for existing worker/tests while orchestration migrates."""
    await call_marketplace_api(session=session, job=job, token=token)
