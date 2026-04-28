from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.wb_report import WbRealizationReport
from utils.batcher import chunks
from utils.date_parser import parse_dt

async def check_wb_report_stats(session: AsyncSession, user_id: str, start_date: date, end_date: date):
    data_check_query = select(func.count(WbRealizationReport.id)).where(
        WbRealizationReport.user_id == user_id,
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date
    )

    data_count = await session.execute(data_check_query)

    return data_count.scalar() or 0

async def get_base_wb_report_stats(session: AsyncSession, user_id: str, start_date: date, end_date: date):
    query = select(
        func.coalesce(func.sum(WbRealizationReport.retail_amount), 0).label("ordered_amount"),
        func.coalesce(func.sum(WbRealizationReport.quantity), 0).label("ordered_units"),
        func.coalesce(func.sum(WbRealizationReport.ppvz_for_pay), 0).label("to_pay"),
        func.coalesce(func.sum(WbRealizationReport.ppvz_sales_commission), 0).label("commission"),
        func.coalesce(func.sum(WbRealizationReport.delivery_rub + WbRealizationReport.return_rub), 0).label("logistics"),
        func.coalesce(func.sum(WbRealizationReport.penalty), 0).label("penalty"),
        func.coalesce(func.sum(WbRealizationReport.additional_payment), 0).label("additional_payment"),
        func.coalesce(func.sum(WbRealizationReport.storage_fee), 0).label("storage_fee")
    ).where(
        WbRealizationReport.user_id == user_id,
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date
    )

    result = await session.execute(query)
    return result.fetchone() 

async def get_sales_wb_report_stats(session: AsyncSession, user_id: str, start_date: date, end_date: date):
    query = select(
        func.sum(WbRealizationReport.retail_amount).label('sales_amount'),
        func.sum(WbRealizationReport.quantity).label('sales_units')
    ).where(
        WbRealizationReport.user_id == user_id,
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date,
        WbRealizationReport.supplier_oper_name == 'Продажа'
    )

    result = await session.execute(query)
    return result.fetchone()

async def get_returns_wb_report_stats(session: AsyncSession, user_id: str, start_date: date, end_date: date):
    query = select(
        func.sum(WbRealizationReport.retail_amount).label('returns_amount'),
        func.sum(WbRealizationReport.quantity).label('returns_units')
    ).where(
        WbRealizationReport.user_id == user_id,
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date,
        WbRealizationReport.supplier_oper_name == 'Возврат'
    )

    result = await session.execute(query)
    stats = result.fetchone()
    print(stats)
    return stats

from datetime import datetime
from sqlalchemy.dialects.postgresql import insert

from models.wb_report import WbRealizationReport

def pick(item: dict, *keys: str) -> Any:
    """Берёт первое НЕ None значение из списка ключей"""
    for k in keys:
        if k in item and item[k] is not None:
            return item[k]
    return None

# ------------------------
# helpers
# ------------------------

def to_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default

    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value)

    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return default

    return default


def to_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value is None:
        return default

    try:
        return Decimal(str(value).replace(",", "."))
    except Exception:
        return default


def to_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def parse_dt_safe(value: Any) -> Optional[datetime]:
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            # если у тебя уже есть parse_dt — можешь использовать его
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return None

    return None

# ------------------------
# нормализатор
# ------------------------
def normalize_wb_report_item(item: dict, user_id: UUID, token_id: UUID) -> dict:
    return {
        "user_id": user_id,
        "token_id": token_id,

        # dates
        "rr_dt": parse_dt_safe(pick(item, "rr_dt", "rrDate")),
        "order_dt": parse_dt_safe(pick(item, "order_dt", "orderDt")),
        "sale_dt": parse_dt_safe(pick(item, "sale_dt", "saleDt")),

        # ids
        "nm_id": to_int(pick(item, "nm_id", "nmId")),
        "rrd_id": to_int(pick(item, "rrd_id", "rrdId")),
        "srid": to_str(pick(item, "srid")),

        # operation
        "supplier_oper_name": to_str(pick(item, "supplier_oper_name", "sellerOperName")),

        # minimal business data
        "office_name": to_str(pick(item, "office_name", "officeName")),

        # facts
        "quantity": to_int(pick(item, "quantity")),
        "retail_amount": to_decimal(pick(item, "retail_amount", "retailAmount")),
        "ppvz_for_pay": to_decimal(pick(item, "ppvz_for_pay", "forPay")),

        # audit
        "created_at": datetime.now(timezone.utc),
    }

async def save_realization(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID,
    data: list[dict],
):
    if not data:
        return

    values = []

    for item in data:
        values.append(normalize_wb_report_item(item, user_id, token_id))

    BATCH_SIZE = 500
    for batch in chunks(data, BATCH_SIZE):
        stmt = insert(WbRealizationReport).values(batch)

        # ❗ ключевая часть — НЕ обновляем, просто игнорим дубли
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["rrd_id", 'user_id']
        )

        await session.execute(stmt)