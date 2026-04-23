from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from models.subscription_model import Subscription
from models.tokens_model import APIToken
from models.user_sync_state_model import UserSyncState
from models.users_model import User

ALL_ENTITIES = ["stocks", "realization", "orders", "sales"]

async def ensure_states_exist(session: AsyncSession):
    # получаем всех активных пользователей с токенами и подпиской
    stmt = (
        select(User.id)
        .where(
            User.is_active == True,
            exists().where(APIToken.user_id == User.id),
            exists().where(Subscription.user_id == User.id)
        )
    )

    result = await session.execute(stmt)
    user_ids = [row[0] for row in result]

    rows = []
    for user_id in user_ids:
        for entity in ALL_ENTITIES:
            rows.append({
                "user_id": user_id,
                "entity": entity
            })

    if not rows:
        return

    stmt = insert(UserSyncState).values(rows)
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["user_id", "entity"]
    )

    await session.execute(stmt)
    await session.commit()