from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from services.payload_builder import build_payload_for_entity
from services.sync_job_service import create_sync_job
from services.user_sync_state_service import SYNC_ENTITIES, ensure_token_sync_states


async def bootstrap_token_sync(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID,
) -> tuple[int, int]:
    """Создаёт состояния и первичные устойчивые задачи нового кабинета Wildberries."""
    states_created = await ensure_token_sync_states(
        session=session,
        user_id=user_id,
        token_id=token_id,
    )

    jobs_created = 0
    for entity in SYNC_ENTITIES:
        payload = build_payload_for_entity(entity)
        created = await create_sync_job(
            session=session,
            user_id=user_id,
            token_id=token_id,
            entity=entity,
            payload=payload,
        )
        jobs_created += int(created)

    return states_created, jobs_created
