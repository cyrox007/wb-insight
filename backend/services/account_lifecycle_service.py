import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.account_lifecycle import AccountLifecycleEvent, PasswordResetToken
from models.subscription_model import Subscription, SubscriptionStatus
from models.tokens_model import APIToken
from models.users_model import User
from settings import config
from utils.hashed_password import hash_password


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def record_lifecycle_event(
    session: AsyncSession,
    *,
    user_id: UUID | None,
    event_type: str,
    actor_user_id: UUID | None = None,
    reason: str | None = None,
    reference_id: str | None = None,
    event_data: dict | None = None,
) -> AccountLifecycleEvent:
    event = AccountLifecycleEvent(
        user_id=user_id,
        actor_user_id=actor_user_id,
        event_type=event_type,
        reason=reason,
        reference_id=reference_id,
        event_data=event_data or {},
    )
    session.add(event)
    await session.flush()
    return event


async def issue_password_reset_token(
    session: AsyncSession,
    user: User,
) -> str:
    now = datetime.now(timezone.utc)
    await session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    raw_token = secrets.token_urlsafe(32)
    token = PasswordResetToken(
        user_id=user.id,
        token_hash=_token_hash(raw_token),
        expires_at=now + timedelta(minutes=config.PASSWORD_RESET_TOKEN_TTL_MINUTES),
    )
    session.add(token)
    await record_lifecycle_event(
        session,
        user_id=user.id,
        event_type="password_reset_requested",
    )
    await session.flush()
    return raw_token


async def reset_password(
    session: AsyncSession,
    *,
    raw_token: str,
    new_password: str,
) -> User | None:
    if len(new_password) < 8 or len(new_password) > 256:
        raise ValueError("Пароль должен содержать от 8 до 256 символов")
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(PasswordResetToken)
        .where(PasswordResetToken.token_hash == _token_hash(raw_token))
        .with_for_update()
    )
    reset_token = result.scalar_one_or_none()
    if (
        reset_token is None
        or reset_token.used_at is not None
        or reset_token.expires_at <= now
    ):
        return None

    user_result = await session.execute(
        select(User).where(User.id == reset_token.user_id).with_for_update()
    )
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None

    user.hashed_password = hash_password(new_password)
    user.session_version += 1
    await session.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    await record_lifecycle_event(
        session,
        user_id=user.id,
        event_type="password_reset_completed",
    )
    await session.flush()
    return user


async def revoke_user_sessions(
    session: AsyncSession,
    user: User,
    *,
    actor_user_id: UUID | None = None,
    reason: str | None = None,
) -> None:
    user.session_version += 1
    await record_lifecycle_event(
        session,
        user_id=user.id,
        actor_user_id=actor_user_id,
        event_type="sessions_revoked",
        reason=reason,
    )
    await session.flush()


async def deactivate_account(
    session: AsyncSession,
    user: User,
    *,
    actor_user_id: UUID | None = None,
    reason: str | None = None,
) -> bool:
    if not user.is_active:
        return False
    now = datetime.now(timezone.utc)
    clean_reason = (reason or "").strip()[:1000] or None
    user.is_active = False
    user.deactivated_at = now
    user.deactivation_reason = clean_reason
    user.retention_until = now + timedelta(days=config.ACCOUNT_DEACTIVATION_RETENTION_DAYS)
    user.session_version += 1

    await session.execute(
        update(APIToken)
        .where(APIToken.user_id == user.id)
        .values(is_active=False, is_revoked=True)
    )
    await session.execute(
        update(Subscription)
        .where(
            Subscription.user_id == user.id,
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.DEMO]),
        )
        .values(
            cancel_at_period_end=True,
            cancel_requested_at=now,
            cancel_reason="account_deactivated",
        )
    )
    await record_lifecycle_event(
        session,
        user_id=user.id,
        actor_user_id=actor_user_id,
        event_type="account_deactivated",
        reason=clean_reason,
        event_data={"retention_until": user.retention_until.isoformat()},
    )
    await session.flush()
    return True


async def reactivate_account(
    session: AsyncSession,
    user: User,
    *,
    actor_user_id: UUID,
    reason: str | None = None,
) -> bool:
    if user.is_active:
        return False
    user.is_active = True
    user.deactivated_at = None
    user.deactivation_reason = None
    user.retention_until = None
    user.session_version += 1
    await record_lifecycle_event(
        session,
        user_id=user.id,
        actor_user_id=actor_user_id,
        event_type="account_reactivated",
        reason=(reason or "").strip()[:1000] or None,
    )
    await session.flush()
    return True


async def request_subscription_cancellation(
    session: AsyncSession,
    *,
    user_id: UUID,
    reason: str | None = None,
) -> Subscription | None:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status.in_([SubscriptionStatus.ACTIVE, SubscriptionStatus.DEMO]),
            Subscription.current_period_end > now,
        )
        .order_by(Subscription.current_period_end.desc())
        .limit(1)
        .with_for_update()
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        return None
    subscription.cancel_at_period_end = True
    subscription.cancel_requested_at = now
    subscription.cancel_reason = (reason or "").strip()[:1000] or None
    await record_lifecycle_event(
        session,
        user_id=user_id,
        event_type="subscription_cancellation_requested",
        reason=subscription.cancel_reason,
        reference_id=str(subscription.id),
        event_data={"access_until": subscription.current_period_end.isoformat()},
    )
    await session.flush()
    return subscription


async def withdraw_subscription_cancellation(
    session: AsyncSession,
    *,
    user_id: UUID,
) -> Subscription | None:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(Subscription)
        .where(
            Subscription.user_id == user_id,
            Subscription.status == SubscriptionStatus.ACTIVE,
            Subscription.current_period_end > now,
            Subscription.cancel_at_period_end.is_(True),
        )
        .order_by(Subscription.current_period_end.desc())
        .limit(1)
        .with_for_update()
    )
    subscription = result.scalar_one_or_none()
    if subscription is None:
        return None
    subscription.cancel_at_period_end = False
    subscription.cancel_requested_at = None
    subscription.cancel_reason = None
    await record_lifecycle_event(
        session,
        user_id=user_id,
        event_type="subscription_cancellation_withdrawn",
        reference_id=str(subscription.id),
    )
    await session.flush()
    return subscription


async def list_lifecycle_events(
    session: AsyncSession,
    *,
    user_id: UUID,
    limit: int = 100,
) -> list[AccountLifecycleEvent]:
    result = await session.execute(
        select(AccountLifecycleEvent)
        .where(AccountLifecycleEvent.user_id == user_id)
        .order_by(AccountLifecycleEvent.created_at.desc())
        .limit(min(max(limit, 1), 200))
    )
    return list(result.scalars().all())
