from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select

from core.database import Database
from core.logger import setup_logger
from models.subscription_model import Subscription
from models.tariffs_model import TariffLimit, TariffPlan
from models.tokens_model import APIToken
from models.users_model import User, UserRoleAssociation


logger = setup_logger(__name__, "operation_diagnostics.log")


def _datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _token_snapshot(token: APIToken) -> dict[str, Any]:
    marketplace = getattr(token.marketplace, "value", str(token.marketplace))
    return {
        "id": str(token.id),
        "marketplace": marketplace,
        "token_type": token.token_type,
        "external_account_id": token.external_account_id,
        "label": token.label,
        "issued_at": _datetime(token.issued_at),
        "expires_at": _datetime(token.expires_at),
        "is_active": bool(token.is_active),
        "is_revoked": bool(token.is_revoked),
        "is_expired": bool(token.is_expired),
        "is_valid": bool(token.is_valid),
    }


async def build_operation_user_snapshot(user_id: UUID) -> dict[str, Any]:
    """Фиксирует несекретное состояние профиля на момент HTTP-запроса."""

    session = await Database.get_session()
    try:
        user = await session.get(User, user_id)
        if user is None:
            return {"user_id": str(user_id), "status": "not_found"}

        roles_result = await session.execute(
            select(UserRoleAssociation.role)
            .where(UserRoleAssociation.user_id == user_id)
            .order_by(UserRoleAssociation.role)
        )
        roles = [str(value) for value in roles_result.scalars().all()]

        subscription_result = await session.execute(
            select(Subscription, TariffPlan)
            .join(TariffPlan, TariffPlan.id == Subscription.tariff_id)
            .where(Subscription.user_id == user_id)
            .order_by(desc(Subscription.current_period_end), desc(Subscription.created_at))
            .limit(1)
        )
        subscription_row = subscription_result.first()
        subscription_snapshot = None
        if subscription_row is not None:
            subscription, tariff = subscription_row
            limits_result = await session.execute(
                select(TariffLimit)
                .where(TariffLimit.tariff_id == tariff.id)
                .order_by(TariffLimit.limit_type)
            )
            limits = {
                item.limit_type: item.limit_value
                for item in limits_result.scalars().all()
            }
            subscription_snapshot = {
                "id": str(subscription.id),
                "status": subscription.status.value,
                "period_start": _datetime(subscription.current_period_start),
                "period_end": _datetime(subscription.current_period_end),
                "cancel_at_period_end": bool(subscription.cancel_at_period_end),
                "is_active_now": bool(subscription.is_active),
                "tariff": {
                    "id": str(tariff.id),
                    "code": tariff.code,
                    "name": tariff.name,
                    "is_active": bool(tariff.is_active),
                    "is_public": bool(tariff.is_public),
                    "limits": limits,
                },
            }

        tokens_result = await session.execute(
            select(APIToken)
            .where(APIToken.user_id == user_id)
            .order_by(APIToken.issued_at, APIToken.id)
        )
        tokens = [_token_snapshot(item) for item in tokens_result.scalars().all()]

        return {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "user": {
                "id": str(user.id),
                "email": user.email,
                "phone": user.phone,
                "full_name": user.full_name,
                "entity_type": user.entity_type,
                "inn": user.inn,
                "kpp": user.kpp,
                "tax_rate": user.tax_rate,
                "timezone": user.timezone,
                "is_active": bool(user.is_active),
                "is_staff": bool(user.is_staff),
                "roles": roles,
                "session_version": int(user.session_version),
            },
            "subscription": subscription_snapshot,
            "marketplace_credentials": tokens,
        }
    except Exception:
        logger.exception(
            "Не удалось собрать снимок контекста пользователя user_id=%s",
            user_id,
        )
        return {
            "user_id": str(user_id),
            "status": "snapshot_error",
        }
    finally:
        await session.close()
