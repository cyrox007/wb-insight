from uuid import UUID
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.sync_job_model import SyncJob

async def create_sync_job(session: AsyncSession, user_id: UUID, entity: str):
    stmt = insert(SyncJob).values(
        user_id=user_id,
        entity=entity,
        payload={},  # или что тебе нужно
        status="pending",
    )

    stmt = stmt.on_conflict_do_nothing(
        index_elements=["user_id", "entity", "is_active"]
    )

    await session.execute(stmt)