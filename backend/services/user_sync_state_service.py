from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select,exists, and_, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from models.user_sync_state_model import UserSyncState
from models.users_model import User
from models.subscription_model import Subscription, SubscriptionStatus
from models.tokens_model import APIToken
from models.tariffs_model import TariffPlan


async def get_states_batch(session: AsyncSession, last_created_at: datetime|None, last_id: UUID|None, limit: int) -> list[UserSyncState]:
    now = datetime.now(timezone.utc)
    stmt = (
        select(UserSyncState)
        .join(User)
        .where(
            User.is_active == True,

            # Есть подписка
            exists().where(
                and_(
                    Subscription.user_id == User.id,
                    Subscription.status == SubscriptionStatus.ACTIVE
                )
            ),

            # И есть токен
            exists().where(
                and_(
                    APIToken.user_id == User.id,
                    APIToken.is_active == True,
                    APIToken.expires_at > now 
                )
            )
        )
        .order_by(UserSyncState.created_at)
        .limit(limit)
    )

    if last_created_at:
        stmt = stmt.where(
            or_(
                UserSyncState.created_at > last_created_at,
                and_(
                    UserSyncState.created_at == last_created_at,
                    UserSyncState.id > last_id
                )
            )
        )

    stmt = stmt.options(
        selectinload(UserSyncState.user)
            .selectinload(User.api_tokens),
        
        selectinload(UserSyncState.user)
            .selectinload(User.subscriptions)
            .selectinload(Subscription.tariff)
            .selectinload(TariffPlan.limits)
    )

    result = await session.execute(stmt)
    states: list[UserSyncState] = list(result.scalars().unique().all())
    return states


async def get_state(session: AsyncSession, user_id: UUID, entity_code: str) -> UserSyncState:
    query = select(UserSyncState).where(
        and_(
            UserSyncState.user_id == user_id,
            UserSyncState.entity == entity_code
        )
    )

    result = await session.execute(query)
    return result.scalar_one()

async def get_user_sync_states(session: AsyncSession, user_id: UUID) -> list[UserSyncState]:
    query = select(UserSyncState).where(
        UserSyncState.user_id == user_id
    )

    result = await session.execute(query)
    return list(result.scalars().unique().all())