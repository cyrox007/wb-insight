from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from services.marketplace_access_service import get_allowed_wb_tokens


class DashboardAccountUnavailableError(ValueError):
    """Requested marketplace account is not available to the current user."""


async def resolve_dashboard_token_id(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID | None,
) -> UUID | None:
    """Validate an optional WB account filter against effective tariff access.

    None means the backward-compatible aggregate over all user facts. A concrete
    token must be one of the currently valid WB accounts allowed by the tariff.
    The same error is used for foreign, expired and over-quota accounts so the
    API does not disclose whether another user's credential exists.
    """
    if token_id is None:
        return None

    allowed_tokens = await get_allowed_wb_tokens(session, user_id)
    if token_id not in {token.id for token in allowed_tokens}:
        raise DashboardAccountUnavailableError(
            "Кабинет Wildberries недоступен для текущего пользователя или тарифа"
        )
    return token_id
