from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.sync_job_model import SyncJob
from settings import config


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _lease_deadline(now: datetime | None = None) -> datetime:
    current = now or _now()
    return current + timedelta(seconds=config.SYNC_JOB_LEASE_SECONDS)


def retry_delay_seconds(attempt_count: int) -> int:
    exponent = max(0, attempt_count - 1)
    delay = config.SYNC_JOB_RETRY_BASE_SECONDS * (2**exponent)
    return min(delay, config.SYNC_JOB_RETRY_MAX_SECONDS)


async def create_sync_job(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID,
    entity: str,
    payload: dict | None = None,
) -> bool:
    """Create one active job per marketplace credential + entity."""
    now = _now()
    stmt = (
        insert(SyncJob)
        .values(
            user_id=user_id,
            token_id=token_id,
            entity=entity,
            payload=payload or {},
            status="pending",
            is_active=True,
            attempt_count=0,
            available_at=now,
        )
        .on_conflict_do_nothing()
        .returning(SyncJob.id)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def recover_stale_jobs(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> tuple[int, int]:
    """Release expired processing leases or fail jobs with exhausted attempts.

    Returns `(requeued, failed)`.
    """
    current = now or _now()
    stmt = (
        select(SyncJob)
        .where(
            SyncJob.status == "processing",
            SyncJob.is_active == True,
            SyncJob.lease_expires_at.is_not(None),
            SyncJob.lease_expires_at <= current,
        )
        .order_by(SyncJob.lease_expires_at, SyncJob.id)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    jobs = list(result.scalars().all())

    requeued = 0
    failed = 0
    for job in jobs:
        job.lease_expires_at = None
        if job.attempt_count >= config.SYNC_JOB_MAX_ATTEMPTS:
            job.status = "failed"
            job.is_active = False
            job.finished_at = current
            job.error = "Worker lease expired and retry budget was exhausted"
            failed += 1
            continue

        job.status = "pending"
        job.started_at = None
        job.available_at = current
        job.error = "Worker lease expired; job requeued"
        requeued += 1

    if jobs:
        await session.flush()
    return requeued, failed


async def claim_next_job(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> SyncJob | None:
    """Atomically claim one due job using SKIP LOCKED."""
    current = now or _now()
    stmt = (
        select(SyncJob)
        .where(
            SyncJob.status == "pending",
            SyncJob.is_active == True,
            SyncJob.available_at <= current,
        )
        .order_by(SyncJob.available_at, SyncJob.created_at, SyncJob.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        return None

    job.status = "processing"
    job.started_at = current
    job.finished_at = None
    job.lease_expires_at = _lease_deadline(current)
    job.attempt_count = int(job.attempt_count or 0) + 1
    job.error = None
    await session.flush()
    return job


async def persist_job_checkpoint(
    session: AsyncSession,
    job: SyncJob,
    payload: dict,
) -> None:
    """Commit one fully persisted page together with its continuation cursor."""
    job.payload = deepcopy(payload)
    job.lease_expires_at = _lease_deadline()
    await session.flush()
    await session.commit()


async def complete_job(
    session: AsyncSession,
    job: SyncJob,
    *,
    now: datetime | None = None,
) -> None:
    current = now or _now()
    job.status = "done"
    job.error = None
    job.is_active = False
    job.lease_expires_at = None
    job.finished_at = current
    await session.flush()


async def retry_job(
    session: AsyncSession,
    job: SyncJob,
    error: str,
    *,
    now: datetime | None = None,
) -> None:
    current = now or _now()
    delay = retry_delay_seconds(job.attempt_count)
    job.status = "pending"
    job.error = error[:1000]
    job.started_at = None
    job.finished_at = None
    job.lease_expires_at = None
    job.available_at = current + timedelta(seconds=delay)
    job.is_active = True
    await session.flush()


async def fail_job(
    session: AsyncSession,
    job: SyncJob,
    error: str,
    *,
    now: datetime | None = None,
) -> None:
    current = now or _now()
    job.status = "failed"
    job.error = error[:1000]
    job.is_active = False
    job.lease_expires_at = None
    job.finished_at = current
    await session.flush()


# Compatibility helpers retained for existing tests/callers. New worker code uses
# claim_next_job so jobs are never pre-claimed as a batch.
async def get_next_jobs(
    session: AsyncSession,
    limit: int = 10,
) -> list[SyncJob]:
    current = _now()
    stmt = (
        select(SyncJob)
        .where(
            SyncJob.status == "pending",
            SyncJob.is_active == True,
            SyncJob.available_at <= current,
        )
        .order_by(SyncJob.available_at, SyncJob.created_at, SyncJob.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def mark_jobs_processing(
    session: AsyncSession,
    jobs: list[SyncJob],
) -> None:
    now = _now()
    for job in jobs:
        job.status = "processing"
        job.started_at = now
        if hasattr(job, "attempt_count"):
            job.attempt_count = int(getattr(job, "attempt_count", 0) or 0) + 1
        if hasattr(job, "lease_expires_at"):
            job.lease_expires_at = _lease_deadline(now)
    await session.flush()
