import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.lifecycle_config import lifecycle_config as config
from models.mail_delivery import EmailVerificationToken
from models.subscription_model import Subscription
from models.users_model import User
from services.account_lifecycle_service import record_lifecycle_event
from services.subscription_service import create_demo_subscription


def token_hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def issue_email_verification_token(session: AsyncSession, user: User) -> str:
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
            token_hash=token_hash(raw_token),
            expires_at=now + timedelta(minutes=config.EMAIL_VERIFICATION_TOKEN_TTL_MINUTES),
        )
    )
    await record_lifecycle_event(
        session,
        user_id=user.id,
        event_type="email_verification_token_issued",
    )
    await session.flush()
    return raw_token


async def verify_email(session: AsyncSession, raw_token: str) -> User | None:
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(EmailVerificationToken)
        .where(EmailVerificationToken.token_hash == token_hash(raw_token))
        .with_for_update()
    )
    token = result.scalar_one_or_none()
    if (
        token is None
        or token.used_at is not None
        or token.revoked_at is not None
        or token.expires_at <= now
    ):
        return None

    user_result = await session.execute(
        select(User).where(User.id == token.user_id).with_for_update()
    )
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None

    if user.email_verified_at is None:
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
        )

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
