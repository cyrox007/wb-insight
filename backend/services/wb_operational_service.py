from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from integrations.wildberries.operational_normalizer import (
    normalize_order_row,
    normalize_sale_row,
)
from models.wb_operational import WbOrder, WbSale
from utils.batcher import chunks


logger = setup_logger(__name__, "wb_api_processor.log")
BATCH_SIZE = 1000


def _normalize_page(
    data: list[dict[str, Any]],
    user_id: UUID,
    token_id: UUID,
    normalizer: Callable[[dict[str, Any], UUID, UUID], dict[str, Any]],
    entity: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    skipped = 0
    now = datetime.now(timezone.utc)

    for item in data:
        try:
            row = normalizer(item, user_id, token_id)
        except ValueError:
            skipped += 1
            continue
        row["created_at"] = now
        row["updated_at"] = now
        rows.append(row)

    if skipped:
        logger.warning(
            "[%s] skipped rows that violate the documented WB identity/date contract count=%s",
            entity.upper(),
            skipped,
        )
    return rows


async def save_orders(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID,
    data: list[dict[str, Any]],
) -> int:
    rows = _normalize_page(data, user_id, token_id, normalize_order_row, "orders")
    if not rows:
        return 0

    mutable_columns = {
        key
        for key in rows[0]
        if key not in {"user_id", "token_id", "srid", "created_at", "updated_at"}
    }

    for batch in chunks(rows, BATCH_SIZE):
        stmt = insert(WbOrder).values(batch)
        updates = {key: getattr(stmt.excluded, key) for key in mutable_columns}
        updates["updated_at"] = datetime.now(timezone.utc)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_wb_order_account_srid",
            set_=updates,
            where=WbOrder.last_change_date <= stmt.excluded.last_change_date,
        )
        await session.execute(stmt)

    return len(rows)


async def save_sales(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID,
    data: list[dict[str, Any]],
) -> int:
    rows = _normalize_page(data, user_id, token_id, normalize_sale_row, "sales")
    if not rows:
        return 0

    mutable_columns = {
        key
        for key in rows[0]
        if key not in {"user_id", "token_id", "sale_id", "created_at", "updated_at"}
    }

    for batch in chunks(rows, BATCH_SIZE):
        stmt = insert(WbSale).values(batch)
        updates = {key: getattr(stmt.excluded, key) for key in mutable_columns}
        updates["updated_at"] = datetime.now(timezone.utc)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_wb_sale_account_sale_id",
            set_=updates,
            where=WbSale.last_change_date <= stmt.excluded.last_change_date,
        )
        await session.execute(stmt)

    return len(rows)
