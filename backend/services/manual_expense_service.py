from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.manual_expense import ManualExpense
from services.dashboard.account_scope import DashboardAccountScope


def parse_expense_amount(value) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Некорректная сумма расхода") from exc
    if amount <= 0:
        raise ValueError("Сумма расхода должна быть больше нуля")
    return amount


async def get_manual_expense_totals(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
    scope: DashboardAccountScope,
) -> tuple[float, dict[int, float]]:
    conditions = [
        ManualExpense.user_id == user_id,
        ManualExpense.date >= start_date,
        ManualExpense.date <= end_date,
    ]

    total_query = select(func.coalesce(func.sum(ManualExpense.amount), 0)).where(
        *conditions
    )
    total_query = scope.apply(total_query, ManualExpense.token_id)
    total = float((await session.execute(total_query)).scalar_one() or 0)

    by_nm_query = (
        select(
            ManualExpense.nm_id,
            func.coalesce(func.sum(ManualExpense.amount), 0).label("amount"),
        )
        .where(*conditions, ManualExpense.nm_id.is_not(None))
        .group_by(ManualExpense.nm_id)
    )
    by_nm_query = scope.apply(by_nm_query, ManualExpense.token_id)
    rows = (await session.execute(by_nm_query)).all()
    by_nm = {int(row.nm_id): float(row.amount or 0) for row in rows if row.nm_id}
    return total, by_nm


async def list_manual_expenses(
    session: AsyncSession,
    user_id: UUID,
    start_date: date,
    end_date: date,
    scope: DashboardAccountScope,
) -> list[ManualExpense]:
    query = (
        select(ManualExpense)
        .where(
            ManualExpense.user_id == user_id,
            ManualExpense.date >= start_date,
            ManualExpense.date <= end_date,
        )
        .order_by(ManualExpense.date.desc(), ManualExpense.created_at.desc())
    )
    query = scope.apply(query, ManualExpense.token_id)
    return list((await session.execute(query)).scalars().all())


async def get_manual_expense(
    session: AsyncSession,
    user_id: UUID,
    expense_id: UUID,
) -> ManualExpense | None:
    return (
        await session.execute(
            select(ManualExpense).where(
                ManualExpense.id == expense_id,
                ManualExpense.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
