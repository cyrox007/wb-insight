from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from models.subscription_model import SubscriptionStatus
from models.tokens_model import Marketplace
from services.subscription_service import get_active_subscription
from services.tariff_service import get_limit
from services.token_services import get_tokens_by_user_id


async def get_wb_account_limit(
    session: AsyncSession,
    user_id: UUID,
) -> int:
    subscription = await get_active_subscription(session, user_id)
    if subscription is None:
        return 0

    if subscription.status == SubscriptionStatus.DEMO:
        return 1

    tariff_limit = await get_limit(
        session=session,
        tariff_id=subscription.tariff_id,
        limit_type="wb_accounts",
    )
    return max(0, int(tariff_limit.limit_value) if tariff_limit else 1)


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


async def get_wb_account_quota(
    session: AsyncSession,
    user_id: UUID,
) -> dict:
    """Return the effective Wildberries account quota for a user."""
    limit = await get_wb_account_limit(session, user_id)
    if limit <= 0:
        return {
            "allowed": False,
            "code": "SUBSCRIPTION_REQUIRED",
            "limit": 0,
            "used": 0,
        }

    tokens = await get_tokens_by_user_id(session, user_id)
    used = sum(
        1
        for token in tokens
        if token.marketplace == Marketplace.WILDBERRIES and token.is_valid
    )

    return {
        "allowed": used < limit,
        "code": None if used < limit else "TOKEN_LIMIT_EXCEEDED",
        "limit": limit,
        "used": used,
    }
