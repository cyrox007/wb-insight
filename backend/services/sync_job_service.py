from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.sync_job_model import SyncJob


async def create_sync_job(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID,
    entity: str,
    payload: dict | None = None,
) -> bool:
    """Create one active job per marketplace credential + entity.

    The partial unique index protects both pending and processing jobs because
    is_active remains true until the worker finishes the job.
    """
    stmt = (
        insert(SyncJob)
        .values(
            user_id=user_id,
            token_id=token_id,
            entity=entity,
            payload=payload or {},
            status="pending",
            is_active=True,
        )
        .on_conflict_do_nothing()
        .returning(SyncJob.id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def get_next_jobs(
    session: AsyncSession,
    limit: int = 10,
) -> list[SyncJob]:
    stmt = (
        select(SyncJob)
        .where(
            SyncJob.status == "pending",
            SyncJob.is_active == True,
        )
        .order_by(SyncJob.created_at, SyncJob.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def mark_jobs_processing(
    session: AsyncSession,
    jobs: list[SyncJob],
) -> None:
    now = datetime.now(timezone.utc)
    for job in jobs:
        job.status = "processing"
        job.started_at = now
        # Keep active=True while work is in progress so the unique partial
        # index prevents the scheduler from enqueueing a duplicate.

    await session.flush()
