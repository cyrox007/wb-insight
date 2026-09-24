from datetime import datetime, timezone
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from integrations.wildberries.token_metadata import (
    WBTokenValidationError,
    decode_wb_token,
    validate_analytics_permissions,
    validate_cloud_service_token,
)
from integrations.wildberries.token_validation import validate_wb_token_live
from models.tokens_model import APIToken, Marketplace
from settings import config
from utils.token_crypto import (
    TokenDecryptionError,
    decrypt_token_with_legacy_status,
    encrypt_token,
)


async def get_user_token_count(session: AsyncSession, user_id: UUID) -> int:
    """Возвращает количество подключений маркетплейсов пользователя."""
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
) -> APIToken:
    """Проверяет учётные данные Wildberries и сохраняет зашифрованный секрет кабинета."""
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
    session.add(token)
    await session.flush()
    return token


async def check_stored_wb_token(
    session: AsyncSession,
    user_id: UUID,
    token: APIToken,
) -> dict:
    """Повторно проверяет сохранённое подключение Wildberries через API."""

    if token.marketplace != Marketplace.WILDBERRIES:
        raise WBTokenValidationError(
            "MARKETPLACE_NOT_SUPPORTED",
            "Проверка этого маркетплейса пока не поддерживается",
        )

    try:
        raw_token, used_legacy_encryption = decrypt_token_with_legacy_status(
            token.encrypted_token,
            str(user_id),
        )
    except TokenDecryptionError as exc:
        raise WBTokenValidationError(
            "WB_TOKEN_STORAGE_UNREADABLE",
            (
                "Сохранённый токен нельзя прочитать. "
                "Удалите это подключение и добавьте новый токен Wildberries."
            ),
            status_code=409,
        ) from exc

    persistent_invalid_codes = {
        "WB_TOKEN_REJECTED",
        "WB_TOKEN_EXPIRED",
        "WB_TOKEN_PERMISSIONS_MISSING",
        "WB_TOKEN_MUST_BE_READ_ONLY",
        "WB_PERSONAL_TOKEN_NOT_ALLOWED",
        "WB_TEST_TOKEN_NOT_SUPPORTED",
        "WB_SERVICE_TOKEN_MISMATCH",
        "WB_TOKEN_UNSUPPORTED_TYPE",
        "WB_TOKEN_MALFORMED",
    }

    try:
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
    except WBTokenValidationError as exc:
        if exc.code not in persistent_invalid_codes:
            raise

        token.is_active = False
        token.is_revoked = exc.code == "WB_TOKEN_REJECTED"
        if used_legacy_encryption:
            token.encrypted_token = encrypt_token(raw_token, str(user_id))
        await session.flush()
        connection_status = "inactive"
        if exc.code == "WB_TOKEN_REJECTED":
            connection_status = "revoked"
        if exc.code == "WB_TOKEN_EXPIRED":
            connection_status = "expired"

        return {
            "valid": False,
            "connection_status": connection_status,
            "code": exc.code,
            "message": str(exc),
        }
    finally:
        del raw_token

    token.token_type = metadata.token_type
    token.external_account_id = metadata.seller_id
    token.expires_at = metadata.expires_at
    token.is_active = True
    token.is_revoked = False
    if used_legacy_encryption:
        token.encrypted_token = encrypt_token(raw_token, str(user_id))
    await session.flush()

    return {
        "valid": True,
        "connection_status": "active",
        "code": None,
        "message": "Подключение Wildberries активно и подтверждено через API.",
    }


async def get_tokens_by_user_id(
    session: AsyncSession,
    user_id: UUID,
) -> Sequence[APIToken]:
    """Возвращает подключения маркетплейсов пользователя."""
    result = await session.execute(
        select(APIToken).where(APIToken.user_id == user_id)
    )
    return result.scalars().all()


async def get_token_by_id(
    session: AsyncSession,
    token_id: UUID,
) -> Optional[APIToken]:
    """Возвращает подключение маркетплейса по идентификатору."""
    result = await session.execute(
        select(APIToken).where(APIToken.id == token_id)
    )
    return result.scalar_one_or_none()


async def delete_token(session: AsyncSession, token: APIToken) -> None:
    """Удаляет подключение маркетплейса, не скрывая ошибки транзакции."""
    await session.delete(token)
    await session.flush()
