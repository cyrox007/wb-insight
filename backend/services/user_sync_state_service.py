from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.subscription_model import Subscription, SubscriptionStatus
from models.tariffs_model import TariffPlan
from models.tokens_model import APIToken
from models.user_sync_state_model import UserSyncState
from models.users_model import User


async def get_states_batch(
    session: AsyncSession,
    last_created_at: datetime | None,
    last_id: UUID | None,
    limit: int,
) -> list[UserSyncState]:
    """Return account-scoped states in stable keyset order.

    The cursor is local to one scheduler run; no process-global scheduling
    state is required, so restarts and multiple workers do not lose rows.
    """
    now = datetime.now(timezone.utc)
    stmt = (
        select(UserSyncState)
        .join(User, User.id == UserSyncState.user_id)
        .join(APIToken, APIToken.id == UserSyncState.token_id)
        .where(
            User.is_active == True,
            APIToken.user_id == User.id,
            APIToken.is_active == True,
            APIToken.is_revoked == False,
            APIToken.expires_at > now,
            exists().where(
                and_(
                    Subscription.user_id == User.id,
                    Subscription.status.in_(
                        [SubscriptionStatus.ACTIVE, SubscriptionStatus.DEMO]
                    ),
                    Subscription.current_period_start <= now,
                    Subscription.current_period_end > now,
                )
            ),
        )
        .order_by(UserSyncState.created_at, UserSyncState.id)
        .limit(limit)
        .options(
            selectinload(UserSyncState.token),
            selectinload(UserSyncState.user)
            .selectinload(User.subscriptions)
            .selectinload(Subscription.tariff)
            .selectinload(TariffPlan.limits),
        )
    )

    if last_created_at is not None and last_id is not None:
        stmt = stmt.where(
            or_(
                UserSyncState.created_at > last_created_at,
                and_(
                    UserSyncState.created_at == last_created_at,
                    UserSyncState.id > last_id,
                ),
            )
        )

    result = await session.execute(stmt)
    return list(result.scalars().unique().all())


async def get_state(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID,
    entity_code: str,
) -> UserSyncState:
    query = select(UserSyncState).where(
        UserSyncState.user_id == user_id,
        UserSyncState.token_id == token_id,
        UserSyncState.entity == entity_code,
    )
    result = await session.execute(query)
    return result.scalar_one()


async def get_user_sync_states(
    session: AsyncSession,
    user_id: UUID,
) -> list[UserSyncState]:
    query = select(UserSyncState).where(UserSyncState.user_id == user_id)
    result = await session.execute(query)
    return list(result.scalars().unique().all())
