from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.subscription_model import Subscription, SubscriptionStatus
from models.tariffs_model import TariffPlan
from models.tokens_model import APIToken
from models.user_sync_state_model import UserSyncState
from models.users_model import User


SYNC_ENTITIES = (
    "stocks",
    "realization",
    "finance_summary",
    "products",
    "prices",
    "orders",
    "sales",
    "advertising",
    "sales_funnel",
    "paid_storage",
)

SYNC_ENTITY_LABELS = {
    "stocks": "Остатки",
    "realization": "Финансовая детализация",
    "finance_summary": "Финансовые отчёты",
    "products": "Товары",
    "prices": "Цены",
    "orders": "Заказы",
    "sales": "Продажи",
    "advertising": "Реклама",
    "sales_funnel": "Воронка",
    "paid_storage": "Платное хранение",
}


def build_sync_status(
    states: list[UserSyncState],
    token_ids: tuple[UUID, ...],
    *,
    is_syncing: bool = False,
) -> dict:
    """Формирует безопасную сводку свежести данных по выбранным кабинетам."""
    expected_accounts = len(token_ids)
    token_id_set = set(token_ids)
    grouped: dict[str, list[UserSyncState]] = defaultdict(list)

    for state in states:
        if state.token_id in token_id_set and state.entity in SYNC_ENTITIES:
            grouped[state.entity].append(state)

    entities = []
    all_success_times: list[datetime] = []

    for entity in SYNC_ENTITIES:
        entity_states = grouped.get(entity, [])
        success_times = [
            state.last_success_at
            for state in entity_states
            if state.last_success_at is not None
        ]
        error_count = sum(1 for state in entity_states if state.last_error)
        successful_accounts = len(success_times)

        if (
            expected_accounts > 0
            and len(entity_states) >= expected_accounts
            and successful_accounts >= expected_accounts
            and error_count == 0
        ):
            status = "ready"
        elif successful_accounts > 0:
            status = "stale"
        elif error_count > 0:
            status = "error"
        else:
            status = "waiting"

        oldest_success_at = min(success_times) if success_times else None
        latest_success_at = max(success_times) if success_times else None
        if oldest_success_at is not None:
            all_success_times.append(oldest_success_at)

        entities.append(
            {
                "entity": entity,
                "label": SYNC_ENTITY_LABELS[entity],
                "status": status,
                "expected_accounts": expected_accounts,
                "successful_accounts": successful_accounts,
                "error_accounts": error_count,
                "oldest_success_at": oldest_success_at,
                "latest_success_at": latest_success_at,
            }
        )

    ready_entities = sum(1 for item in entities if item["status"] == "ready")
    stale_entities = sum(1 for item in entities if item["status"] == "stale")
    error_entities = sum(1 for item in entities if item["status"] == "error")
    waiting_entities = sum(1 for item in entities if item["status"] == "waiting")

    return {
        "is_syncing": is_syncing,
        "expected_accounts": expected_accounts,
        "total_entities": len(SYNC_ENTITIES),
        "ready_entities": ready_entities,
        "stale_entities": stale_entities,
        "error_entities": error_entities,
        "waiting_entities": waiting_entities,
        "complete": ready_entities == len(SYNC_ENTITIES),
        "oldest_success_at": min(all_success_times) if all_success_times else None,
        "latest_success_at": max(
            (
                item["latest_success_at"]
                for item in entities
                if item["latest_success_at"] is not None
            ),
            default=None,
        ),
        "entities": entities,
    }


async def ensure_token_sync_states(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID,
) -> int:
    """Создаёт недостающие состояния синхронизации для одного WB-кабинета."""
    rows = [
        {
            "user_id": user_id,
            "token_id": token_id,
            "entity": entity,
        }
        for entity in SYNC_ENTITIES
    ]
    if not rows:
        return 0

    stmt = (
        insert(UserSyncState)
        .values(rows)
        .on_conflict_do_nothing(
            index_elements=["user_id", "token_id", "entity"],
        )
        .returning(UserSyncState.id)
    )
    result = await session.execute(stmt)
    return len(result.scalars().all())


async def get_states_batch(
    session: AsyncSession,
    last_created_at: datetime | None,
    last_id: UUID | None,
    limit: int,
) -> list[UserSyncState]:
    """Возвращает состояния кабинетов в стабильном порядке пагинации.

    Курсор существует только внутри одного прохода планировщика. Глобальное
    состояние процесса не используется, поэтому рестарты и несколько обработчиков
    не приводят к потере строк.
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
