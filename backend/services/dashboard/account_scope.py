from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import false
from sqlalchemy.ext.asyncio import AsyncSession

from core.operation_context import get_operation_context
from services.marketplace_access_service import get_allowed_wb_tokens
from services.operation_log_service import persist_current_operation_event


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


async def _trace_scope(
    *,
    user_id: UUID,
    requested_token_id: UUID | None,
    allowed_ids: tuple[UUID, ...],
    allowed: bool,
) -> None:
    if get_operation_context() is None:
        return
    await persist_current_operation_event(
        domain="access",
        operation="dashboard_account_scope",
        step="account_scope_resolved" if allowed else "account_scope_denied",
        status="success" if allowed else "warning",
        severity="info" if allowed else "warning",
        event_kind="access_decision",
        component="dashboard_scope",
        direction="internal",
        user_id=user_id,
        subject_type="wb_credential" if requested_token_id else "user",
        subject_id=requested_token_id or user_id,
        error_code=None if allowed else "WB_ACCOUNT_UNAVAILABLE",
        message=(
            "Определён набор кабинетов Wildberries для расчёта"
            if allowed
            else "Запрошенный кабинет Wildberries не разрешён пользователю или тарифу"
        ),
        input_data={"requested_token_id": requested_token_id},
        output_data={
            "allowed_token_ids": list(allowed_ids),
            "selected_token_id": requested_token_id if allowed else None,
            "allowed": allowed,
        },
    )


async def resolve_dashboard_scope(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID | None,
) -> DashboardAccountScope:
    """Ограничивает данные дашборда кабинетами WB, разрешёнными текущим тарифом."""
    allowed_tokens = await get_allowed_wb_tokens(session, user_id)
    allowed_ids = tuple(token.id for token in allowed_tokens)

    if token_id is not None and token_id not in allowed_ids:
        await _trace_scope(
            user_id=user_id,
            requested_token_id=token_id,
            allowed_ids=allowed_ids,
            allowed=False,
        )
        raise DashboardAccountUnavailableError(
            "Кабинет Wildberries недоступен для текущего пользователя или тарифа"
        )

    await _trace_scope(
        user_id=user_id,
        requested_token_id=token_id,
        allowed_ids=allowed_ids,
        allowed=True,
    )
    return DashboardAccountScope(
        token_ids=(token_id,) if token_id is not None else allowed_ids,
        selected_token_id=token_id,
    )