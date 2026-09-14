import asyncio

from sqlalchemy import exists, select
from sqlalchemy.dialects.postgresql import insert

from celery_app import celery_app
from core.database_celery import get_session
from core.logger import setup_logger
from models.tokens_model import APIToken
from models.user_sync_state_model import UserSyncState
from models.users_model import User
from services.marketplace_access_service import get_allowed_wb_tokens


logger = setup_logger(__name__, "create_state_scheduler.log")

ALL_ENTITIES = [
    "stocks",
    "realization",
    "products",
    # "orders",
    # "sales",
]


async def ensure_states_exist() -> None:
    session = await get_session()
    try:
        result = await session.execute(
            select(User.id).where(
                User.is_active == True,
                exists().where(APIToken.user_id == User.id),
            )
        )
        user_ids = [row[0] for row in result]

        rows: list[dict] = []
        for user_id in user_ids:
            tokens = await get_allowed_wb_tokens(session, user_id)
            for token in tokens:
                for entity in ALL_ENTITIES:
                    rows.append(
                        {
                            "user_id": user_id,
                            "token_id": token.id,
                            "entity": entity,
                        }
                    )

        if not rows:
            return

        stmt = insert(UserSyncState).values(rows)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["user_id", "token_id", "entity"]
        )
        await session.execute(stmt)
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("Failed to ensure account-scoped sync states")
        raise
    finally:
        await session.close()


@celery_app.task(name="tasks.schedulers.create_state_scheduler.schedule_sync")
def schedule_sync():
    asyncio.run(ensure_states_exist())
