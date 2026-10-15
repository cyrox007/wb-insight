from copy import deepcopy
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.operation_context import get_operation_context
from models.sync_job_model import SyncJob
from services.operation_log_service import record_operation_event
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
    """Создаёт не более одной активной задачи на кабинет и тип данных."""
    now = _now()
    job_payload = payload or {}
    stmt = (
        insert(SyncJob)
        .values(
            user_id=user_id,
            token_id=token_id,
            entity=entity,
            payload=job_payload,
            status="pending",
            is_active=True,
            attempt_count=0,
            available_at=now,
        )
        .on_conflict_do_nothing()
        .returning(SyncJob.id)
    )
    result = await session.execute(stmt)
    job_id = result.scalar_one_or_none()
    if job_id is None:
        return False

    context = get_operation_context()
    parent_operation_id = None
    actor_user_id = None
    request_id = None
    if context is not None:
        actor_user_id = context.actor_user_id
        request_id = context.request_id
        if context.operation_id != job_id:
            parent_operation_id = context.operation_id

    await record_operation_event(
        session,
        operation_id=job_id,
        parent_operation_id=parent_operation_id,
        domain="sync",
        operation="marketplace_sync",
        step="job_created",
        status="started",
        user_id=user_id,
        actor_user_id=actor_user_id,
        subject_type="sync_job",
        subject_id=job_id,
        provider="wildberries",
        request_id=request_id,
        message=f"Создана задача синхронизации '{entity}'",
        input_data={
            "token_id": token_id,
            "entity": entity,
            "checkpoint": job_payload,
        },
    )
    return True


async def recover_stale_jobs(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> tuple[int, int]:
    """Возвращает просроченные задачи в очередь или завершает исчерпанные."""
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
        expired_at = job.lease_expires_at
        job.lease_expires_at = None
        if job.attempt_count >= config.SYNC_JOB_MAX_ATTEMPTS:
            job.status = "failed"
            job.is_active = False
            job.finished_at = current
            job.error = "Истекла аренда worker, лимит повторов исчерпан"
            failed += 1
            await record_operation_event(
                session,
                operation_id=job.id,
                domain="sync",
                operation="marketplace_sync",
                step="lease_expired",
                status="failed",
                severity="error",
                user_id=job.user_id,
                subject_type="sync_job",
                subject_id=job.id,
                provider="wildberries",
                error_code="SYNC_RETRY_BUDGET_EXHAUSTED",
                message="Задача остановлена после истечения аренды и исчерпания повторов",
                metrics={
                    "entity": job.entity,
                    "attempt_count": job.attempt_count,
                    "lease_expires_at": expired_at,
                },
            )
            continue

        job.status = "pending"
        job.started_at = None
        job.available_at = current
        job.error = "Истекла аренда worker; задача возвращена в очередь"
        requeued += 1
        await record_operation_event(
            session,
            operation_id=job.id,
            domain="sync",
            operation="marketplace_sync",
            step="lease_recovered",
            status="warning",
            severity="warning",
            user_id=job.user_id,
            subject_type="sync_job",
            subject_id=job.id,
            provider="wildberries",
            message="Просроченная задача возвращена в очередь",
            metrics={
                "entity": job.entity,
                "attempt_count": job.attempt_count,
                "lease_expires_at": expired_at,
            },
        )

    if jobs:
        await session.flush()
    return requeued, failed


async def claim_next_job(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> SyncJob | None:
    """Атомарно забирает одну готовую задачу через SKIP LOCKED."""
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
    await record_operation_event(
        session,
        operation_id=job.id,
        domain="sync",
        operation="marketplace_sync",
        step="attempt_started",
        status="started",
        user_id=job.user_id,
        subject_type="sync_job",
        subject_id=job.id,
        provider="wildberries",
        message=f"Начата попытка синхронизации '{job.entity}'",
        metrics={
            "entity": job.entity,
            "attempt_count": job.attempt_count,
            "max_attempts": config.SYNC_JOB_MAX_ATTEMPTS,
            "lease_expires_at": job.lease_expires_at,
        },
    )
    await session.flush()
    return job


async def persist_job_checkpoint(
    session: AsyncSession,
    job: SyncJob,
    payload: dict,
) -> None:
    """Фиксирует полностью сохранённую страницу вместе с курсором продолжения."""
    job.payload = deepcopy(payload)
    job.lease_expires_at = _lease_deadline()
    await record_operation_event(
        session,
        operation_id=job.id,
        domain="sync",
        operation="marketplace_sync",
        step="checkpoint_saved",
        status="info",
        user_id=job.user_id,
        subject_type="sync_job",
        subject_id=job.id,
        provider="wildberries",
        message=f"Сохранена контрольная точка синхронизации '{job.entity}'",
        metrics={
            "entity": job.entity,
            "attempt_count": job.attempt_count,
            "checkpoint": payload,
        },
    )
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
    duration_ms = None
    if job.started_at is not None:
        duration_ms = max(0, int((current - job.started_at).total_seconds() * 1000))
    await record_operation_event(
        session,
        operation_id=job.id,
        domain="sync",
        operation="marketplace_sync",
        step="completed",
        status="success",
        user_id=job.user_id,
        subject_type="sync_job",
        subject_id=job.id,
        provider="wildberries",
        duration_ms=duration_ms,
        message=f"Синхронизация '{job.entity}' завершена",
        metrics={
            "entity": job.entity,
            "attempt_count": job.attempt_count,
            "checkpoint": job.payload or {},
        },
    )
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
    await record_operation_event(
        session,
        operation_id=job.id,
        domain="sync",
        operation="marketplace_sync",
        step="retry_scheduled",
        status="warning",
        severity="warning",
        user_id=job.user_id,
        subject_type="sync_job",
        subject_id=job.id,
        provider="wildberries",
        error_code="SYNC_RETRY_SCHEDULED",
        message=error[:1000],
        metrics={
            "entity": job.entity,
            "attempt_count": job.attempt_count,
            "retry_delay_seconds": delay,
            "available_at": job.available_at,
        },
    )
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
    await record_operation_event(
        session,
        operation_id=job.id,
        domain="sync",
        operation="marketplace_sync",
        step="failed",
        status="failed",
        severity="error",
        user_id=job.user_id,
        subject_type="sync_job",
        subject_id=job.id,
        provider="wildberries",
        error_code="SYNC_JOB_FAILED",
        message=error[:1000],
        metrics={
            "entity": job.entity,
            "attempt_count": job.attempt_count,
            "checkpoint": job.payload or {},
        },
    )
    await session.flush()


# Совместимые функции сохранены для существующих тестов и старых вызовов.
# Новый worker забирает задачи по одной через claim_next_job.
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
