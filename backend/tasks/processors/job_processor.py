import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from celery_app import celery_app
from core.database_celery import get_session
from core.logger import setup_logger
from integrations.wildberries.client import (
    WBAPIError,
    WBAuthError,
    WBFeatureUnavailableError,
    WBPermissionError,
    WBRateLimitError,
)
from models.sync_job_model import SyncJob
from models.tokens_model import Marketplace
from services.marketplace_access_service import get_allowed_wb_tokens
from services.operation_log_service import record_operation_event
from services.sync_job_service import (
    claim_next_job,
    complete_job,
    fail_job,
    recover_stale_jobs,
    retry_job,
)
from services.token_services import get_token_by_id
from services.user_sync_state_service import get_state
from settings import config
from sync.router import call_wb_api


logger = setup_logger(__name__, "processor.log")


class PermanentSyncJobError(RuntimeError):
    """Ошибка задачи, которую нельзя исправить повтором без изменения состояния."""


def _auth_error_rejects_credential(exc: WBAuthError) -> bool:
    """Только явный 401 от Wildberries подтверждает недействительность токена."""
    return exc.status_code == 401


def _is_retryable(exc: Exception) -> bool:
    if isinstance(
        exc,
        (
            WBAuthError,
            WBPermissionError,
            WBFeatureUnavailableError,
            PermanentSyncJobError,
            ValueError,
        ),
    ):
        return False
    if isinstance(exc, WBRateLimitError):
        return True
    if isinstance(exc, WBAPIError):
        return exc.status_code is None or exc.status_code >= 500
    return True


def _failure_code(exc: Exception) -> str:
    if isinstance(exc, WBPermissionError):
        return "WB_PERMISSION_DENIED"
    if isinstance(exc, WBFeatureUnavailableError):
        return "WB_FEATURE_UNAVAILABLE"
    if isinstance(exc, WBAuthError):
        return "WB_AUTH_FAILED"
    if isinstance(exc, WBRateLimitError):
        return "WB_RATE_LIMITED"
    if isinstance(exc, WBAPIError):
        return "WB_API_ERROR"
    if isinstance(exc, PermanentSyncJobError):
        return "SYNC_CONFIGURATION_ERROR"
    if isinstance(exc, ValueError):
        return "SYNC_DATA_ERROR"
    return "SYNC_UNEXPECTED_ERROR"


def _failure_step(exc: Exception) -> str:
    return {
        "WB_PERMISSION_DENIED": "wb_permission_denied",
        "WB_FEATURE_UNAVAILABLE": "wb_feature_unavailable",
        "WB_AUTH_FAILED": "wb_auth_failed",
        "WB_RATE_LIMITED": "wb_rate_limited",
        "WB_API_ERROR": "wb_api_error",
        "SYNC_CONFIGURATION_ERROR": "configuration_failed",
        "SYNC_DATA_ERROR": "data_processing_failed",
        "SYNC_UNEXPECTED_ERROR": "unexpected_failure",
    }[_failure_code(exc)]


async def _record_structured_failure(
    session: AsyncSession,
    job: SyncJob,
    exc: Exception,
) -> None:
    endpoint = getattr(exc, "endpoint", None)
    http_status = getattr(exc, "status_code", None)
    await record_operation_event(
        session,
        operation_id=job.id,
        domain="sync",
        operation="marketplace_sync",
        step=_failure_step(exc),
        status="failed" if not _is_retryable(exc) else "warning",
        severity="error" if not _is_retryable(exc) else "warning",
        user_id=job.user_id,
        subject_type="sync_job",
        subject_id=job.id,
        provider="wildberries",
        http_status=http_status,
        error_code=_failure_code(exc),
        message=str(exc)[:1000] or type(exc).__name__,
        output_data={
            "endpoint": endpoint,
            "http_status": http_status,
            "credential_rejected": (
                _auth_error_rejects_credential(exc)
                if isinstance(exc, WBAuthError)
                else False
            ),
        },
        metrics={
            "entity": job.entity,
            "attempt_count": int(job.attempt_count or 0),
            "max_attempts": config.SYNC_JOB_MAX_ATTEMPTS,
            "retryable": _is_retryable(exc),
        },
    )


async def worker_loop(session: AsyncSession, limit: int = 10) -> int:
    """Забирает задачи по одной и восстанавливает потерянные аренды."""
    requeued, stale_failed = await recover_stale_jobs(session)
    if requeued or stale_failed:
        logger.warning(
            "Восстановлены просроченные задачи синхронизации: в очередь=%s завершены=%s",
            requeued,
            stale_failed,
        )
    await session.commit()

    processed = 0
    for _ in range(limit):
        job = await claim_next_job(session)
        if job is None:
            await session.commit()
            break

        job_id = job.id
        await session.commit()

        try:
            await process_job(session, job)
            await complete_job(session, job)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            fresh_job = await session.get(SyncJob, job_id)
            if fresh_job is None:
                logger.error("Забранная задача синхронизации исчезла id=%s", job_id)
                continue

            await _record_failure(session, fresh_job, exc)
            await session.commit()
        finally:
            processed += 1

    return processed


async def process_job(session: AsyncSession, job: SyncJob) -> None:
    """Обрабатывает ровно тот кабинет маркетплейса, который записан в задаче."""
    token = await get_token_by_id(session, job.token_id)
    if token is None or token.user_id != job.user_id:
        raise PermanentSyncJobError("Кабинет синхронизации не найден")
    if token.marketplace != Marketplace.WILDBERRIES or not token.is_valid:
        raise PermanentSyncJobError(
            "Кабинет Wildberries недоступен для синхронизации"
        )

    allowed_tokens = await get_allowed_wb_tokens(session, job.user_id)
    if token.id not in {allowed.id for allowed in allowed_tokens}:
        raise PermanentSyncJobError(
            "Кабинет Wildberries недоступен на текущем тарифе"
        )

    state = await get_state(
        session=session,
        user_id=job.user_id,
        token_id=job.token_id,
        entity_code=job.entity,
    )
    state.last_sync_at = datetime.now(timezone.utc)

    await record_operation_event(
        session,
        operation_id=job.id,
        domain="sync",
        operation="marketplace_sync",
        step="credential_ready",
        status="success",
        user_id=job.user_id,
        subject_type="sync_job",
        subject_id=job.id,
        provider="wildberries",
        message="Подключение прошло локальные проверки и допущено к запросу Wildberries",
        output_data={
            "token_id": token.id,
            "token_type": token.token_type,
            "entity": job.entity,
            "expires_at": token.expires_at,
        },
    )

    try:
        await call_wb_api(session=session, token=token, job=job)
    except WBAuthError as exc:
        if _auth_error_rejects_credential(exc):
            token.is_active = False
            token.is_revoked = True
            state.last_error = (
                "Ошибка авторизации: подключение отозвано или недействительно. "
                "Обновите кабинет Wildberries в настройках."
            )
        else:
            state.last_error = (
                "Синхронизация остановлена из-за серверной конфигурации "
                "авторизации Wildberries. Подключение пользователя не отключено."
            )
        raise

    if job.entity in {"orders", "sales"}:
        source_cursor = (job.payload or {}).get("dateFrom")
        if source_cursor:
            state.source_cursor = {"dateFrom": str(source_cursor)}
    elif job.entity == "paid_storage":
        completed_through = (job.payload or {}).get("completedThrough")
        if completed_through:
            state.source_cursor = {"completedThrough": str(completed_through)}

    state.last_success_at = datetime.now(timezone.utc)
    state.last_error = None


async def _record_failure(
    session: AsyncSession,
    job: SyncJob,
    exc: Exception,
) -> None:
    now = datetime.now(timezone.utc)
    error_text = str(exc)[:1000] or type(exc).__name__

    try:
        state = await get_state(
            session=session,
            user_id=job.user_id,
            token_id=job.token_id,
            entity_code=job.entity,
        )
        state.last_sync_at = now
        state.last_error = error_text
    except Exception:
        state = None
        logger.exception(
            "Не удалось обновить состояние синхронизации после ошибки задачи id=%s",
            job.id,
        )

    await _record_structured_failure(session, job, exc)

    if isinstance(exc, WBAuthError):
        credential_rejected = _auth_error_rejects_credential(exc)
        token = await get_token_by_id(session, job.token_id)
        if token is not None and credential_rejected:
            token.is_active = False
            token.is_revoked = True
        if state is not None:
            state.last_error = (
                "Ошибка авторизации: подключение отозвано или недействительно. "
                "Обновите кабинет Wildberries в настройках."
                if credential_rejected
                else (
                    "Синхронизация остановлена из-за серверной конфигурации "
                    "авторизации Wildberries. Подключение пользователя не отключено."
                )
            )
        await fail_job(session, job, error_text, now=now)
        logger.warning(
            "[ЗАДАЧА %s] Ошибка авторизации WB пользователь=%s подключение=%s "
            "данные=%s статус=%s подключение_отозвано=%s",
            job.id,
            job.user_id,
            job.token_id,
            job.entity,
            exc.status_code,
            credential_rejected,
        )
        return

    if isinstance(exc, WBPermissionError):
        if state is not None:
            state.last_error = (
                "У подключения нет доступа к категории WB API, необходимой "
                f"для синхронизации '{job.entity}'."
            )
        await fail_job(session, job, error_text, now=now)
        logger.warning(
            "[ЗАДАЧА %s] Недостаточно прав WB пользователь=%s подключение=%s данные=%s",
            job.id,
            job.user_id,
            job.token_id,
            job.entity,
        )
        return

    if isinstance(exc, WBFeatureUnavailableError):
        if state is not None:
            state.last_error = (
                "Функция WB API недоступна для текущего тарифа/подписки кабинета "
                f"при синхронизации '{job.entity}'."
            )
        await fail_job(session, job, error_text, now=now)
        logger.warning(
            "[ЗАДАЧА %s] Функция WB недоступна пользователь=%s подключение=%s данные=%s",
            job.id,
            job.user_id,
            job.token_id,
            job.entity,
        )
        return

    if _is_retryable(exc) and job.attempt_count < config.SYNC_JOB_MAX_ATTEMPTS:
        await retry_job(session, job, error_text, now=now)
        logger.warning(
            "[ЗАДАЧА %s] Назначен повтор попытка=%s/%s данные=%s ошибка=%s",
            job.id,
            job.attempt_count,
            config.SYNC_JOB_MAX_ATTEMPTS,
            job.entity,
            type(exc).__name__,
        )
        return

    await fail_job(session, job, error_text, now=now)
    logger.warning(
        "[ЗАДАЧА %s] Окончательная ошибка попытка=%s/%s данные=%s ошибка=%s",
        job.id,
        job.attempt_count,
        config.SYNC_JOB_MAX_ATTEMPTS,
        job.entity,
        type(exc).__name__,
    )


@celery_app.task(name="tasks.processors.job_processor.run")
def run_worker():
    asyncio.run(_run_worker())


async def _run_worker() -> None:
    session = await get_session()
    try:
        await worker_loop(session)
    except Exception:
        await session.rollback()
        logger.exception("Ошибка worker синхронизации")
        raise
    finally:
        await session.close()
