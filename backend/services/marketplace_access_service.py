from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.token_metadata import (
    WBTokenValidationError,
    decode_wb_token,
)
from integrations.wildberries.token_validation import validate_wb_token_live
from models.tokens_model import Marketplace
from services.subscription_service import get_active_subscription
from services.tariff_service import get_limit
from services.token_services import get_tokens_by_user_id
from settings import config
from utils.token_crypto import decrypt_token


logger = setup_logger(__name__)


async def get_wb_account_limit(
    session: AsyncSession,
    user_id: UUID,
) -> int:
    subscription = await get_active_subscription(session, user_id)
    if subscription is None:
        return 0

    tariff_limit = await get_limit(
        session=session,
        tariff_id=subscription.tariff_id,
        limit_type="wb_accounts",
    )
    # Конфигурация тарифа — единственный источник истины для лимита кабинетов.
    # Отсутствующий лимит трактуется как запрет, а не как неявная квота по умолчанию.
    return max(0, int(tariff_limit.limit_value)) if tariff_limit else 0


async def get_wb_sync_frequency_hours(
    session: AsyncSession,
    user_id: UUID,
) -> int | None:
    """Возвращает тарифный интервал синхронизации Wildberries в часах."""
    subscription = await get_active_subscription(session, user_id)
    if subscription is None:
        return None

    tariff_limit = await get_limit(
        session=session,
        tariff_id=subscription.tariff_id,
        limit_type="sync_frequency_hours",
    )
    if tariff_limit is None:
        return None

    return max(1, int(tariff_limit.limit_value))


async def get_allowed_wb_tokens(
    session: AsyncSession,
    user_id: UUID,
):
    """Возвращает только кабинеты Wildberries, разрешённые текущим тарифом.

    Выбор детерминирован, поэтому планировщик и обработчик задач используют
    один и тот же набор кабинетов, даже если сохранённых подключений больше,
    чем разрешено тарифом.
    """
    limit = await get_wb_account_limit(session, user_id)
    if limit <= 0:
        return []

    tokens = await get_tokens_by_user_id(session, user_id)
    valid_tokens = [
        token
        for token in tokens
        if token.marketplace == Marketplace.WILDBERRIES and token.is_valid
    ]
    valid_tokens.sort(
        key=lambda token: (
            token.issued_at,
            str(token.id),
        )
    )
    return valid_tokens[:limit]


async def _probe_stored_wb_token(token, user_id: UUID) -> str:
    """Проверяет сохранённый токен онлайн только когда он занимает всю квоту.

    Возвращает машинное состояние valid, rejected, expired или unknown.
    Состояние unknown намеренно оставляет место занятым: сбой Wildberries,
    отсутствие сервисных реквизитов или локальная ошибка расшифровки не должны
    считаться доказательством отзыва токена.
    """
    raw_token = None
    try:
        raw_token = decrypt_token(token.encrypted_token, str(user_id))
        metadata = decode_wb_token(raw_token)
        await validate_wb_token_live(
            raw_token,
            metadata,
            service_secret=config.WB_SERVICE_SECRET,
        )
        return "valid"
    except WBTokenValidationError as exc:
        if exc.code == "WB_TOKEN_REJECTED":
            return "rejected"
        if exc.code == "WB_TOKEN_EXPIRED":
            return "expired"

        logger.warning(
            "Онлайн-проверка квоты Wildberries не дала однозначного результата идентификатор_токена=%s код=%s",
            token.id,
            exc.code,
        )
        return "unknown"
    except Exception as exc:
        logger.warning(
            "Онлайн-проверка квоты Wildberries завершилась ошибкой идентификатор_токена=%s тип_ошибки=%s",
            token.id,
            type(exc).__name__,
        )
        return "unknown"
    finally:
        if raw_token is not None:
            del raw_token


async def _release_stale_wb_quota(
    session: AsyncSession,
    user_id: UUID,
    tokens,
) -> int:
    """Освобождает места квоты для подтверждённо недействительных WB-токенов."""
    released = 0

    for token in tokens:
        probe = await _probe_stored_wb_token(token, user_id)

        if probe == "rejected":
            token.is_active = False
            token.is_revoked = True
            released += 1
            logger.info(
                "Токен Wildberries исключён из квоты после подтверждённого отказа идентификатор_токена=%s",
                token.id,
            )
        elif probe == "expired":
            token.is_active = False
            released += 1
            logger.info(
                "Токен Wildberries исключён из квоты после истечения срока идентификатор_токена=%s",
                token.id,
            )

    if released:
        await session.flush()

    return released


async def get_wb_account_quota(
    session: AsyncSession,
    user_id: UUID,
) -> dict:
    """Возвращает фактическую квоту кабинетов Wildberries для пользователя.

    Удалённо отозванный токен может локально выглядеть действующим до истечения
    срока JWT. Когда квота заполнена, выполняется ограниченная онлайн-проверка.
    Подтверждённый отказ Wildberries помечает токен отозванным, чтобы он не
    блокировал подключение нового кабинета.
    """
    limit = await get_wb_account_limit(session, user_id)
    if limit <= 0:
        return {
            "allowed": False,
            "code": "SUBSCRIPTION_REQUIRED",
            "limit": 0,
            "used": 0,
        }

    tokens = await get_tokens_by_user_id(session, user_id)
    valid_tokens = [
        token
        for token in tokens
        if token.marketplace == Marketplace.WILDBERRIES and token.is_valid
    ]
    used = len(valid_tokens)

    # В обычном случае проверяем квоту локально. К Wildberries обращаемся только
    # если сохранённое состояние иначе запретило бы подключить замену.
    if used >= limit and valid_tokens:
        released = await _release_stale_wb_quota(
            session,
            user_id,
            valid_tokens,
        )
        used = max(0, used - released)

    return {
        "allowed": used < limit,
        "code": None if used < limit else "TOKEN_LIMIT_EXCEEDED",
        "limit": limit,
        "used": used,
    }
