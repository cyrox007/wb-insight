import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.lifecycle_config import lifecycle_config as config
from models.account_lifecycle import PasswordResetToken
from models.mail_delivery import EmailVerificationToken
from models.subscription_model import Subscription
from models.users_model import User
from services.account_lifecycle_service import record_lifecycle_event
from services.subscription_service import create_demo_subscription


class EmailVerificationTargetConflict(RuntimeError):
    """Raised when a verified target email already belongs to another account."""


def token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _normalized_email(value: str | None) -> str:
    return str(value or "").strip().lower()


def _verification_target(user: User, requested_email: str | None = None) -> str:
    target = _normalized_email(requested_email)
    current = _normalized_email(user.email)
    pending = _normalized_email(getattr(user, "pending_email", None))

    if not target:
        target = pending or current

    registration_target = target == current and user.email_verified_at is None
    change_target = bool(pending) and target == pending
    if not registration_target and not change_target:
        raise ValueError("email_verification_target_stale")
    return target


async def issue_email_verification_token(
    session: AsyncSession,
    user: User,
    *,
    email: str | None = None,
) -> str:
    """Create a one-time token bound to the exact address being verified."""
    target = _verification_target(user, email)
    now = datetime.now(timezone.utc)
    await session.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    raw_token = secrets.token_urlsafe(32)
    session.add(
        EmailVerificationToken(
            user_id=user.id,
            email=target,
            token_hash=token_hash(raw_token),
            expires_at=now + timedelta(minutes=config.EMAIL_VERIFICATION_TOKEN_TTL_MINUTES),
        )
    )
    await record_lifecycle_event(
        session,
        user_id=user.id,
        event_type="email_verification_token_issued",
        event_data={"purpose": "email_change" if target != _normalized_email(user.email) else "registration"},
    )
    await session.flush()
    return raw_token


async def verify_email(session: AsyncSession, raw_token: str) -> User | None:
    """Verify registration email or atomically apply a pending email change.

    Replaying the same successfully-used token is idempotent while that verified
    address is still the account's current identity. Revoked, expired or stale
    target tokens remain invalid.
    """
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.token_hash == token_hash(raw_token))
        .with_for_update()
    )
    token = result.scalar_one_or_none()
    if token is None or token.revoked_at is not None or token.expires_at <= now:
        return None

    user_result = await session.execute(
        select(User).where(User.id == token.user_id).with_for_update()
    )
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None

    target = _normalized_email(token.email)
    current = _normalized_email(user.email)
    pending = _normalized_email(getattr(user, "pending_email", None))

    if token.used_at is not None:
        if target == current and user.email_verified_at is not None:
            return user
        return None

    if target == current and user.email_verified_at is None:
        # Initial registration: grant demo access only after ownership is proven.
        user.email_verified_at = now
        subscription_result = await session.execute(
            select(Subscription.id).where(Subscription.user_id == user.id).limit(1)
        )
        if subscription_result.scalar_one_or_none() is None:
            await create_demo_subscription(session, user.id)
        await record_lifecycle_event(
            session,
            user_id=user.id,
            event_type="email_verified",
            event_data={"purpose": "registration"},
        )
    elif pending and target == pending:
        # Protect the final write with both an explicit lookup and the existing
        # users.email UNIQUE constraint. The handler maps a racing IntegrityError
        # to a stable conflict response instead of leaking a 500.
        conflicting = await session.execute(
            select(User.id)
            .where(User.id != user.id, func.lower(User.email) == target)
            .limit(1)
            .with_for_update()
        )
        if conflicting.scalar_one_or_none() is not None:
            raise EmailVerificationTargetConflict("email_already_in_use")

        user.email = target
        user.pending_email = None
        user.email_verified_at = now
        user.session_version += 1

        # A reset link delivered to the previous address must never survive an
        # email identity change. Session-version rotation invalidates JWTs too.
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
            event_type="email_changed",
            event_data={"verified": True},
        )
    else:
        # The address changed again after this token was issued, or the token
        # targets an already-verified current address. Treat it as stale.
        return None

    token.used_at = now
    await session.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.id != token.id,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    await session.flush()
    return user



async def admin_verify_email(
    session: AsyncSession,
    user: User,
    *,
    actor_user_id,
    reason: str | None = None,
) -> bool:
    """Mark the current account email as verified from the control panel.

    This is intentionally an audited administrative escape hatch for support
    cases where normal mail delivery is unavailable. It verifies only the
    current email identity, cancels stale pending-email capabilities, and grants
    the same demo entitlement as the normal registration verification flow.
    """
    if user.email_verified_at is not None:
        return False

    now = datetime.now(timezone.utc)
    user.email_verified_at = now
    user.pending_email = None

    await session.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )

    subscription_result = await session.execute(
        select(Subscription.id).where(Subscription.user_id == user.id).limit(1)
    )
    if subscription_result.scalar_one_or_none() is None:
        await create_demo_subscription(session, user.id)

    await record_lifecycle_event(
        session,
        user_id=user.id,
        actor_user_id=actor_user_id,
        event_type="email_verified_manual",
        reason=(reason or "").strip()[:1000] or None,
        event_data={"source": "control_panel"},
    )
    await session.flush()
    return True
