from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import AsyncSession

from integrations.wildberries.paid_storage_normalizer import normalize_paid_storage_rows
from models.wb_paid_storage import WbPaidStorage
from utils.batcher import chunks


BATCH_SIZE = 1000


async def replace_paid_storage_period(
    session: AsyncSession,
    *,
    user_id: UUID,
    token_id: UUID,
    task_id: str | None,
    start_date: date,
    end_date: date,
    data: list[dict[str, Any]],
) -> int:
    """Replace one completed WB report period inside the current transaction."""
    if end_date < start_date:
        raise ValueError("paid storage end_date must be on or after start_date")

    rows = normalize_paid_storage_rows(data, user_id, token_id, task_id)
    rows = [row for row in rows if start_date <= row["date"] <= end_date]

    await session.execute(
        delete(WbPaidStorage).where(
            WbPaidStorage.user_id == user_id,
            WbPaidStorage.token_id == token_id,
            WbPaidStorage.date >= start_date,
            WbPaidStorage.date <= end_date,
        )
    )

    for batch in chunks(rows, BATCH_SIZE):
        await session.execute(insert(WbPaidStorage).values(batch))

    return len(rows)
