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
    """Ошибка конфликта, когда подтверждаемый email уже принадлежит другому аккаунту."""


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


async def revoke_email_verification_tokens(
    session: AsyncSession,
    user_id,
) -> None:
    """Отзывает все неиспользованные токены подтверждения email аккаунта."""
    await session.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )


async def issue_email_verification_token(
    session: AsyncSession,
    user: User,
    *,
    email: str | None = None,
) -> str:
    """Создаёт одноразовый токен, привязанный к конкретному подтверждаемому адресу."""
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
    """Подтверждает email регистрации или атомарно применяет ожидающую смену адреса.

    Повтор уже успешно использованного токена идемпотентен, пока подтверждённый
    адрес остаётся текущей identity аккаунта. Отозванные, истёкшие и устаревшие
    токены остаются недействительными.
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
        # Первичная регистрация: demo-доступ выдаётся только после подтверждения владения адресом.
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
        # Финальную запись защищают и явный lookup, и существующий UNIQUE users.email.
        # Конкурентный IntegrityError преобразуется handler'ом в стабильный конфликт,
        # а не раскрывается как необработанный 500.
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

        # Ссылка восстановления, отправленная на прежний адрес, не должна переживать
        # смену email identity. Ротация session_version также отзывает старые JWT.
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
        # После выпуска токена адрес снова изменился либо токен указывает на уже
        # подтверждённый текущий адрес. Такой токен считается устаревшим.
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
    """Помечает текущий email аккаунта подтверждённым из панели управления.

    Это журналируемый административный механизм для случаев, когда обычная
    доставка почты недоступна. Он подтверждает только текущую email identity,
    отменяет устаревшие pending-email возможности и выдаёт тот же demo-доступ,
    что и штатное подтверждение регистрации.
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



async def admin_change_email_identity(
    session: AsyncSession,
    user: User,
    *,
    new_email: str,
    actor_user_id,
) -> None:
    """Применяет административную коррекцию email без скрытого сохранения verification.

    Новый адрес становится текущей login identity, но возвращается в
    неподтверждённое состояние. Существующие сессии и возможности
    восстановления/подтверждения отзываются, после чего администратор может
    использовать штатный flow подтверждения или явное журналируемое ручное действие.
    """
    normalized = _normalized_email(new_email)
    if not normalized or "@" not in normalized or len(normalized) > 254:
        raise ValueError("invalid_email")
    if normalized == _normalized_email(user.email):
        return

    now = datetime.now(timezone.utc)
    user.email = normalized
    user.email_verified_at = None
    user.pending_email = None
    user.session_version += 1

    await session.execute(
        update(EmailVerificationToken)
        .where(
            EmailVerificationToken.user_id == user.id,
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
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
        actor_user_id=actor_user_id,
        event_type="email_changed_by_admin",
        event_data={"source": "control_panel", "verified": False},
    )
    await session.flush()
