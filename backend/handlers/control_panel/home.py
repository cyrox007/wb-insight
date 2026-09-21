from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Request

from core.access_control import Permission
from core.authorization import require_permission
from core.dependencies import get_db_session
from core.ops_config import ops_config
from models.mail_delivery import MailMessage, MailStatus
from models.payments_model import Payment, PaymentStatus
from models.users_model import User
from services.operational_monitoring_service import build_operational_snapshot
from services.user_service import get_user_count
from utils.responce_helps import response_success


router = APIRouter(
    prefix='/control-panel',
    tags=['Control Panel'],
    dependencies=[Depends(require_permission(Permission.CONTROL_PANEL_ACCESS))],
)


async def _count(db_session: AsyncSession, statement) -> int:
    result = await db_session.execute(statement)
    return int(result.scalar_one() or 0)


async def _account_health(db_session: AsyncSession) -> dict[str, int]:
    result = await db_session.execute(
        select(
            func.count(User.id).label("total"),
            func.count(User.id).filter(User.is_active.is_(True)).label("active"),
            func.count(User.id).filter(User.is_active.is_(False)).label("inactive"),
            func.count(User.id).filter(User.email_verified_at.is_not(None)).label("verified"),
            func.count(User.id).filter(User.email_verified_at.is_(None)).label("unverified"),
            func.count(User.id).filter(User.is_staff.is_(True)).label("staff"),
        )
    )
    row = result.one()
    return {
        "total": int(row.total or 0),
        "active": int(row.active or 0),
        "inactive": int(row.inactive or 0),
        "verified": int(row.verified or 0),
        "unverified": int(row.unverified or 0),
        "staff": int(row.staff or 0),
    }


async def _client_health(db_session: AsyncSession) -> dict[str, int]:
    """Seller/client account health, explicitly excluding internal staff accounts."""
    result = await db_session.execute(
        select(
            func.count(User.id).filter(User.is_staff.is_(False)).label("total"),
            func.count(User.id).filter(
                User.is_staff.is_(False),
                User.is_active.is_(True),
            ).label("active"),
            func.count(User.id).filter(
                User.is_staff.is_(False),
                User.is_active.is_(False),
            ).label("inactive"),
            func.count(User.id).filter(
                User.is_staff.is_(False),
                User.email_verified_at.is_not(None),
            ).label("verified"),
            func.count(User.id).filter(
                User.is_staff.is_(False),
                User.email_verified_at.is_(None),
            ).label("unverified"),
        )
    )
    row = result.one()
    return {
        "total": int(row.total or 0),
        "active": int(row.active or 0),
        "inactive": int(row.inactive or 0),
        "verified": int(row.verified or 0),
        "unverified": int(row.unverified or 0),
    }


async def _attention_summary(
    db_session: AsyncSession,
    *,
    permissions: set[str],
    account_health: dict[str, int],
    now: datetime | None = None,
) -> dict:
    """Return permission-scoped aggregate attention signals without PII."""
    current = now or datetime.now(timezone.utc)
    summary: dict[str, dict] = {}

    if Permission.USERS_READ.value in permissions:
        summary["users"] = {
            "unverified": int(account_health.get("unverified") or 0),
            "inactive": int(account_health.get("inactive") or 0),
        }

    if Permission.MAIL_READ.value in permissions:
        failure_cutoff = current - timedelta(
            minutes=ops_config.MAIL_FAILURE_LOOKBACK_MINUTES
        )
        stale_cutoff = current - timedelta(
            minutes=ops_config.MAIL_QUEUE_STALE_MINUTES
        )
        failed_recent = await _count(
            db_session,
            select(func.count())
            .select_from(MailMessage)
            .where(
                MailMessage.status == MailStatus.FAILED.value,
                MailMessage.last_attempt_at.is_not(None),
                MailMessage.last_attempt_at >= failure_cutoff,
            ),
        )
        stale_queued = await _count(
            db_session,
            select(func.count())
            .select_from(MailMessage)
            .where(
                MailMessage.status == MailStatus.QUEUED.value,
                MailMessage.created_at <= stale_cutoff,
                MailMessage.next_attempt_at <= current,
            ),
        )
        summary["mail"] = {
            "failed_recent": failed_recent,
            "stale_queued": stale_queued,
            "failure_lookback_minutes": ops_config.MAIL_FAILURE_LOOKBACK_MINUTES,
            "queue_stale_minutes": ops_config.MAIL_QUEUE_STALE_MINUTES,
        }

    if Permission.PAYMENTS_READ.value in permissions:
        payment_cutoff = current - timedelta(hours=24)
        failed_recent = await _count(
            db_session,
            select(func.count())
            .select_from(Payment)
            .where(
                Payment.status == PaymentStatus.FAILED,
                Payment.updated_at >= payment_cutoff,
            ),
        )
        stale_pending = await _count(
            db_session,
            select(func.count())
            .select_from(Payment)
            .where(
                Payment.status == PaymentStatus.PENDING,
                Payment.created_at <= payment_cutoff,
            ),
        )
        summary["payments"] = {
            "failed_24h": failed_recent,
            "pending_over_24h": stale_pending,
        }

    if Permission.SYSTEM_MANAGE.value in permissions:
        snapshot = await build_operational_snapshot(db_session, now=current)
        checks = snapshot.get("checks") or {}
        issue_count = sum(
            1
            for check in checks.values()
            if check.get("status") in {"warning", "critical", "error"}
        )
        summary["system"] = {
            "status": snapshot.get("status", "unknown"),
            "issue_count": issue_count,
        }

    return summary


@router.get('/')
async def get_control_panel(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
):
    permissions = set(getattr(request.state, "permissions", set()))
    account_health = await _account_health(db_session)
    client_health = await _client_health(db_session)
    user_count = (
        await get_user_count(db_session)
        if Permission.USERS_READ.value in permissions
        else None
    )
    return response_success(
        user_count=user_count,
        account_health=account_health,
        client_health=client_health,
        attention=await _attention_summary(
            db_session,
            permissions=permissions,
            account_health=client_health,
        ),
        permissions=sorted(permissions),
    )
