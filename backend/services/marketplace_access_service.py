from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from models.subscription_model import SubscriptionStatus
from models.tokens_model import Marketplace
from services.subscription_service import get_active_subscription
from services.tariff_service import get_limit
from services.token_services import get_tokens_by_user_id


async def get_wb_account_quota(
    session: AsyncSession,
    user_id: UUID,
) -> dict:
    """Return the effective Wildberries account quota for a user.

    The server is the source of truth for tariff enforcement. Frontend checks
    are only UX hints and cannot grant additional accounts.
    """
    subscription = await get_active_subscription(session, user_id)
    if subscription is None:
        return {
            "allowed": False,
            "code": "SUBSCRIPTION_REQUIRED",
            "limit": 0,
            "used": 0,
        }

    if subscription.status == SubscriptionStatus.DEMO:
        limit = 1
    else:
        tariff_limit = await get_limit(
            session=session,
            tariff_id=subscription.tariff_id,
            limit_type="wb_accounts",
        )
        limit = int(tariff_limit.limit_value) if tariff_limit else 1

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
