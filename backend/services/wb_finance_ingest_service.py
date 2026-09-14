from typing import Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from integrations.wildberries.finance_normalizer import normalize_finance_row
from models.wb_report import WbRealizationReport
from utils.batcher import chunks


async def save_realization(
    session: AsyncSession,
    user_id: UUID,
    account_id: UUID,
    data: list[dict[str, Any]],
) -> None:
    if not data:
        return

    values = [normalize_finance_row(item, user_id, account_id) for item in data]

    for batch in chunks(values, 500):
        stmt = insert(WbRealizationReport).values(batch)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["token_id", "rrd_id"]
        )
        await session.execute(stmt)
