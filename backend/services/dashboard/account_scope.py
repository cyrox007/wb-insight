from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import false
from sqlalchemy.ext.asyncio import AsyncSession

from services.marketplace_access_service import get_allowed_wb_tokens


class DashboardAccountUnavailableError(ValueError):
    """Выбранный кабинет маркетплейса недоступен текущему пользователю."""


@dataclass(frozen=True)
class DashboardAccountScope:
    token_ids: tuple[UUID, ...]
    selected_token_id: UUID | None = None

    def apply(self, query, token_column):
        if not self.token_ids:
            return query.where(false())
        return query.where(token_column.in_(self.token_ids))

    def contains(self, token_id: UUID) -> bool:
        return token_id in self.token_ids


async def resolve_dashboard_scope(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID | None,
) -> DashboardAccountScope:
    """Ограничивает данные дашборда кабинетами WB, разрешёнными текущим тарифом."""
    allowed_tokens = await get_allowed_wb_tokens(session, user_id)
    allowed_ids = tuple(token.id for token in allowed_tokens)

    if token_id is not None and token_id not in allowed_ids:
        raise DashboardAccountUnavailableError(
            "Кабинет Wildberries недоступен для текущего пользователя или тарифа"
        )

    return DashboardAccountScope(
        token_ids=(token_id,) if token_id is not None else allowed_ids,
        selected_token_id=token_id,
    )
