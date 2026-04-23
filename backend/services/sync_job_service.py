from datetime import datetime,timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.sync_job_model import SyncJob

async def create_sync_job(session: AsyncSession, user_id: UUID, entity: str):
    stmt = insert(SyncJob).values(
        user_id=user_id,
        entity=entity,
        payload={},  # или что тебе нужно
        status="pending",
    )

    stmt = stmt.on_conflict_do_nothing(
        index_elements=["user_id", "entity", "is_active"]
    )

    await session.execute(stmt)

async def get_next_jobs(session: AsyncSession, limit: int = 10) -> list[SyncJob]:
    stmt = (
        select(SyncJob)
        .where(
            SyncJob.status == "pending",
            SyncJob.is_active == True
        )
        .order_by(SyncJob.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )

    result = await session.execute(stmt)
    jobs: list[SyncJob] = list(result.scalars().all())

    return jobs

async def mark_jobs_processing(session: AsyncSession, jobs: list[SyncJob]):
    now = datetime.now(timezone.utc)

    for job in jobs:
        job.status = "processing"
        job.started_at = now

    await session.flush()