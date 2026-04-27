from datetime import datetime,timezone
from uuid import UUID
from sqlalchemy import and_, exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from models.sync_job_model import SyncJob

async def create_sync_job(session: AsyncSession, user_id: UUID, entity: str, payload: dict = {}):
    stmt = insert(SyncJob).values(
        user_id=user_id,
        entity=entity,
        payload=payload,
        status="pending",
        is_active=True
    )

    stmt = stmt.on_conflict_do_nothing()

    await session.execute(stmt)

async def get_next_jobs(session: AsyncSession, limit: int = 10) -> list[SyncJob]:
    sj2 = aliased(SyncJob)

    stmt = (
        select(SyncJob)
        .where(
            SyncJob.status == "pending",
            SyncJob.is_active == True,
        )
        .order_by(SyncJob.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )

    result = await session.execute(stmt)
    return list(result.scalars().all())

async def mark_jobs_processing(session: AsyncSession, jobs: list[SyncJob]):
    now = datetime.now(timezone.utc)

    for job in jobs:
        job.status = "processing"
        job.started_at = now
        job.is_active = False

    await session.flush()