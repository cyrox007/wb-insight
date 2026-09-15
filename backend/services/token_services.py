from datetime import datetime, timezone
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.token_metadata import (
    WBTokenValidationError,
    decode_wb_token,
    validate_analytics_permissions,
    validate_cloud_service_token,
)
from integrations.wildberries.token_validation import validate_wb_token_live
from models.tokens_model import APIToken, Marketplace
from settings import config
from utils.token_crypto import encrypt_token


logger = setup_logger(__name__)


async def get_user_token_count(session: AsyncSession, user_id: UUID) -> int:
    """Получаем количество токенов, добавленных пользователем."""
    result = await session.execute(
        select(APIToken).where(APIToken.user_id == user_id)
    )
    return len(result.scalars().all())


async def insert_token(
    session: AsyncSession,
    user_id: UUID,
    raw_token: str,
    marketplace_code: str = "wb",
    label: str = "Токен для аналитики",
) -> Optional[APIToken]:
    """Validate a WB credential and store the encrypted marketplace secret."""

    normalized_marketplace = marketplace_code.strip().lower()
    if normalized_marketplace not in {"wb", "wildberries"}:
        raise WBTokenValidationError(
            "MARKETPLACE_NOT_SUPPORTED",
            "Подключение этого маркетплейса пока не поддерживается",
        )

    metadata = decode_wb_token(raw_token)
    validate_cloud_service_token(
        metadata,
        service_id=config.WB_SERVICE_ID,
        service_secret_configured=bool(config.WB_SERVICE_SECRET),
    )
    validate_analytics_permissions(metadata)
    await validate_wb_token_live(
        raw_token,
        metadata,
        service_secret=config.WB_SERVICE_SECRET,
    )

    token = APIToken(
        user_id=user_id,
        marketplace=Marketplace.WILDBERRIES,
        token_type=metadata.token_type,
        external_account_id=metadata.seller_id,
        encrypted_token=encrypt_token(raw_token, str(user_id)),
        label=label,
        issued_at=datetime.now(timezone.utc),
        expires_at=metadata.expires_at,
    )

    try:
        session.add(token)
        await session.flush()
        return token
    except Exception as exc:
        logger.error("Ошибка при добавлении токена: %s", exc)
        return None


async def get_tokens_by_user_id(
    session: AsyncSession,
    user_id: UUID,
) -> Sequence[APIToken]:
    """Получаем токены пользователя."""
    result = await session.execute(
        select(APIToken).where(APIToken.user_id == user_id)
    )
    return result.scalars().all()


async def get_token_by_id(
    session: AsyncSession,
    token_id: UUID,
) -> Optional[APIToken]:
    """Получаем токен по id."""
    result = await session.execute(
        select(APIToken).where(APIToken.id == token_id)
    )
    return result.scalar_one_or_none()


async def delete_token(session: AsyncSession, token: APIToken) -> bool:
    """Удаляем токен."""
    try:
        await session.delete(token)
        await session.flush()
        return True
    except Exception as exc:
        logger.error("Ошибка при удалении токена: %s", exc)
        return False
