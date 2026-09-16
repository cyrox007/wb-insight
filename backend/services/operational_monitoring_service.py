from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.http_metrics import read_http_counters
from core.lifecycle_config import lifecycle_config
from core.ops_config import ops_config
from core.version import APP_VERSION
from models.mail_delivery import MailMessage, MailStatus
from models.sync_job_model import SyncJob
from models.tokens_model import APIToken
from models.user_sync_state_model import UserSyncState
from settings import config


def _check(status: str, **values) -> dict:
    return {"status": status, **values}


def summarize_operational_status(checks: dict[str, dict]) -> str:
    statuses = {check.get("status") for check in checks.values()}
    if "critical" in statuses or "error" in statuses:
        return "degraded"
    if "warning" in statuses:
        return "warning"
    return "ok"


def _wb_service_secret_check(current: datetime, warning_days: int) -> dict:
    """Return rotation status without ever exposing the service secret itself."""
    if not config.WB_SERVICE_SECRET:
        return _check("not_applicable", configured=False)

    raw_expiry = ops_config.WB_SERVICE_SECRET_EXPIRES_AT
    if not raw_expiry:
        return _check(
            "warning",
            configured=True,
            reason="expiry_not_configured",
            warning_days=warning_days,
        )

    try:
        expires_at = datetime.fromisoformat(raw_expiry.replace("Z", "+00:00"))
        if expires_at.tzinfo is None:
            raise ValueError("timezone is required")
        expires_at = expires_at.astimezone(timezone.utc)
    except ValueError:
        return _check(
            "critical",
            configured=True,
            reason="invalid_expiry_config",
            warning_days=warning_days,
        )

    seconds_remaining = (expires_at - current).total_seconds()
    days_remaining = int(seconds_remaining // 86400)
    if seconds_remaining <= 0:
        status = "critical"
    elif expires_at <= current + timedelta(days=warning_days):
        status = "warning"
    else:
        status = "ok"

    return _check(
        status,
        configured=True,
        expires_at=expires_at.isoformat(),
        days_remaining=days_remaining,
        warning_days=warning_days,
    )


async def _count(session: AsyncSession, statement) -> int:
    result = await session.execute(statement)
    return int(result.scalar_one() or 0)


async def _mail_checks(session: AsyncSession, current: datetime) -> tuple[dict, dict]:
    mail_enabled = (
        lifecycle_config.MAIL_DELIVERY_ENABLED
        or lifecycle_config.PASSWORD_RESET_ENABLED
        or lifecycle_config.EMAIL_VERIFICATION_ENABLED
    )
    if not mail_enabled:
        disabled = _check("not_applicable", enabled=False)
        return disabled, disabled.copy()

    failure_cutoff = current - timedelta(minutes=ops_config.MAIL_FAILURE_LOOKBACK_MINUTES)
    stale_cutoff = current - timedelta(minutes=ops_config.MAIL_QUEUE_STALE_MINUTES)
    terminal_statuses = [MailStatus.SENT.value, MailStatus.FAILED.value]

    total_terminal = await _count(
        session,
        select(func.count())
        .select_from(MailMessage)
        .where(
            MailMessage.status.in_(terminal_statuses),
            MailMessage.last_attempt_at.is_not(None),
            MailMessage.last_attempt_at >= failure_cutoff,
        ),
    )
    failed_terminal = await _count(
        session,
        select(func.count())
        .select_from(MailMessage)
        .where(
            MailMessage.status == MailStatus.FAILED.value,
            MailMessage.last_attempt_at.is_not(None),
            MailMessage.last_attempt_at >= failure_cutoff,
        ),
    )
    failure_rate = failed_terminal / total_terminal if total_terminal else 0.0
    failure_status = "ok"
    if (
        total_terminal >= ops_config.MAIL_FAILURE_MIN_MESSAGES
        and failure_rate >= ops_config.MAIL_FAILURE_RATE_THRESHOLD
    ):
        failure_status = "critical"

    stale_queued = await _count(
        session,
        select(func.count())
        .select_from(MailMessage)
        .where(
            MailMessage.status == MailStatus.QUEUED.value,
            MailMessage.created_at <= stale_cutoff,
            MailMessage.next_attempt_at <= current,
        ),
    )
    queue_status = "warning" if stale_queued else "ok"

    return (
        _check(
            failure_status,
            enabled=True,
            messages=total_terminal,
            errors=failed_terminal,
            rate=round(failure_rate, 4),
            lookback_minutes=ops_config.MAIL_FAILURE_LOOKBACK_MINUTES,
            threshold=ops_config.MAIL_FAILURE_RATE_THRESHOLD,
            min_messages=ops_config.MAIL_FAILURE_MIN_MESSAGES,
        ),
        _check(
            queue_status,
            enabled=True,
            count=stale_queued,
            stale_after_minutes=ops_config.MAIL_QUEUE_STALE_MINUTES,
        ),
    )


async def build_operational_snapshot(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> dict:
    current = now or datetime.now(timezone.utc)
    failed_cutoff = current - timedelta(minutes=ops_config.FAILED_JOB_LOOKBACK_MINUTES)
    stale_cutoff = current - timedelta(minutes=ops_config.SYNC_STALE_MINUTES)
    expiry_warning = current + timedelta(days=ops_config.CREDENTIAL_EXPIRY_WARNING_DAYS)

    failed_jobs = await _count(
        session,
        select(func.count())
        .select_from(SyncJob)
        .where(SyncJob.status == "failed", SyncJob.finished_at >= failed_cutoff),
    )
    expired_leases = await _count(
        session,
        select(func.count())
        .select_from(SyncJob)
        .where(
            SyncJob.status == "processing",
            SyncJob.is_active == True,
            SyncJob.lease_expires_at.is_not(None),
            SyncJob.lease_expires_at <= current,
        ),
    )
    stale_sync_states = await _count(
        session,
        select(func.count())
        .select_from(UserSyncState)
        .where(
            or_(
                UserSyncState.last_success_at < stale_cutoff,
                (UserSyncState.last_success_at.is_(None))
                & (UserSyncState.created_at < stale_cutoff),
            )
        ),
    )
    expired_credentials = await _count(
        session,
        select(func.count())
        .select_from(APIToken)
        .where(
            APIToken.is_active == True,
            APIToken.is_revoked == False,
            APIToken.expires_at.is_not(None),
            APIToken.expires_at <= current,
        ),
    )
    expiring_credentials = await _count(
        session,
        select(func.count())
        .select_from(APIToken)
        .where(
            APIToken.is_active == True,
            APIToken.is_revoked == False,
            APIToken.expires_at.is_not(None),
            APIToken.expires_at > current,
            APIToken.expires_at <= expiry_warning,
        ),
    )

    try:
        request_count, error_count = await read_http_counters(
            ops_config.HTTP_ERROR_WINDOW_MINUTES,
            now=current,
        )
        error_rate = error_count / request_count if request_count else 0.0
        http_status = "ok"
        if (
            request_count >= ops_config.HTTP_MIN_REQUESTS
            and error_rate >= ops_config.HTTP_5XX_RATE_THRESHOLD
        ):
            http_status = "critical"
        http_5xx = _check(
            http_status,
            requests=request_count,
            errors=error_count,
            rate=round(error_rate, 4),
            window_minutes=ops_config.HTTP_ERROR_WINDOW_MINUTES,
            threshold=ops_config.HTTP_5XX_RATE_THRESHOLD,
            min_requests=ops_config.HTTP_MIN_REQUESTS,
            enabled=ops_config.HTTP_METRICS_ENABLED,
        )
    except Exception:
        http_5xx = _check(
            "error",
            reason="metrics_unavailable",
            window_minutes=ops_config.HTTP_ERROR_WINDOW_MINUTES,
            enabled=ops_config.HTTP_METRICS_ENABLED,
        )

    try:
        mail_failure_rate, mail_queue_stale = await _mail_checks(session, current)
    except Exception:
        mail_failure_rate = _check("error", reason="mail_metrics_unavailable")
        mail_queue_stale = _check("error", reason="mail_metrics_unavailable")

    checks = {
        "failed_sync_jobs": _check(
            "critical" if failed_jobs else "ok",
            count=failed_jobs,
            lookback_minutes=ops_config.FAILED_JOB_LOOKBACK_MINUTES,
        ),
        "expired_job_leases": _check(
            "critical" if expired_leases else "ok",
            count=expired_leases,
        ),
        "stale_sync_states": _check(
            "critical" if stale_sync_states else "ok",
            count=stale_sync_states,
            stale_after_minutes=ops_config.SYNC_STALE_MINUTES,
        ),
        "expired_credentials": _check(
            "critical" if expired_credentials else "ok",
            count=expired_credentials,
        ),
        "expiring_credentials": _check(
            "warning" if expiring_credentials else "ok",
            count=expiring_credentials,
            warning_days=ops_config.CREDENTIAL_EXPIRY_WARNING_DAYS,
        ),
        "wb_service_secret": _wb_service_secret_check(
            current,
            ops_config.WB_SERVICE_SECRET_EXPIRY_WARNING_DAYS,
        ),
        "http_5xx": http_5xx,
        "mail_failure_rate": mail_failure_rate,
        "mail_queue_stale": mail_queue_stale,
    }

    return {
        "status": summarize_operational_status(checks),
        "version": APP_VERSION,
        "generated_at": current.isoformat(),
        "checks": checks,
    }
