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
    # Tariff configuration is the single source of truth for runtime limits.
    # Missing limits fail closed instead of silently granting a default quota.
    return max(0, int(tariff_limit.limit_value)) if tariff_limit else 0


async def get_allowed_wb_tokens(
    session: AsyncSession,
    user_id: UUID,
):
    """Return only WB tokens allowed by the user's current tariff.

    Selection is deterministic so scheduler and worker cannot disagree about
    which seller accounts are active when the user has more stored tokens than
    their plan permits.
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
    """Live-check a stored credential only when it blocks the account quota.

    Returns valid, rejected, expired or unknown. Unknown deliberately keeps
    the quota occupied: a WB outage, missing service credentials or a local
    decrypt failure must never be interpreted as proof of revocation.
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
            "WB quota live-check was inconclusive token_id=%s code=%s",
            token.id,
            exc.code,
        )
        return "unknown"
    except Exception as exc:
        logger.warning(
            "WB quota live-check failed token_id=%s error=%s",
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
    """Invalidate confirmed stale WB credentials and return released slots."""
    released = 0

    for token in tokens:
        probe = await _probe_stored_wb_token(token, user_id)

        if probe == "rejected":
            token.is_active = False
            token.is_revoked = True
            released += 1
            logger.info(
                "WB credential removed from quota after live rejection token_id=%s",
                token.id,
            )
        elif probe == "expired":
            token.is_active = False
            released += 1
            logger.info(
                "WB credential removed from quota after expiry token_id=%s",
                token.id,
            )

    if released:
        await session.flush()

    return released


async def get_wb_account_quota(
    session: AsyncSession,
    user_id: UUID,
) -> dict:
    """Return the effective Wildberries account quota for a user.

    A credential that has been remotely revoked may still look locally valid
    until its JWT expiry is reached. When the quota is full, perform a bounded
    live revalidation. Confirmed 401 rejections are marked revoked so they
    cannot block adding a replacement credential.
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

    # Keep normal quota checks local. Only touch WB when the stored state would
    # otherwise reject a replacement credential.
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
