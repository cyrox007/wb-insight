from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.wb_report import WbRealizationReport
from services.dashboard.account_scope import DashboardAccountScope


def _scope(query, user_id: UUID, scope: DashboardAccountScope):
    query = query.where(WbRealizationReport.user_id == user_id)
    return scope.apply(query, WbRealizationReport.token_id)


async def get_base_report_stats(session: AsyncSession, user_id: UUID, start_date: date, end_date: date, scope: DashboardAccountScope):
    query = select(
        func.coalesce(func.sum(WbRealizationReport.retail_amount), 0).label("ordered_amount"),
        func.coalesce(func.sum(WbRealizationReport.quantity), 0).label("ordered_units"),
        func.coalesce(func.sum(WbRealizationReport.ppvz_for_pay), 0).label("to_pay"),
        func.coalesce(func.sum(WbRealizationReport.ppvz_sales_commission), 0).label("commission"),
        func.coalesce(func.sum(WbRealizationReport.delivery_rub + WbRealizationReport.return_rub), 0).label("logistics"),
        func.coalesce(func.sum(WbRealizationReport.penalty), 0).label("penalty"),
        func.coalesce(func.sum(WbRealizationReport.additional_payment), 0).label("additional_payment"),
        func.coalesce(func.sum(WbRealizationReport.storage_fee), 0).label("storage_fee"),
    ).where(WbRealizationReport.rr_dt >= start_date, WbRealizationReport.rr_dt <= end_date)
    return (await session.execute(_scope(query, user_id, scope))).one()


async def get_sales_report_stats(session: AsyncSession, user_id: UUID, start_date: date, end_date: date, scope: DashboardAccountScope):
    query = select(
        func.coalesce(func.sum(WbRealizationReport.retail_amount), 0).label("sales_amount"),
        func.coalesce(func.sum(WbRealizationReport.quantity), 0).label("sales_units"),
    ).where(
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date,
        WbRealizationReport.supplier_oper_name == "Продажа",
    )
    return (await session.execute(_scope(query, user_id, scope))).one()


async def get_returns_report_stats(session: AsyncSession, user_id: UUID, start_date: date, end_date: date, scope: DashboardAccountScope):
    query = select(
        func.coalesce(func.sum(WbRealizationReport.retail_amount), 0).label("returns_amount"),
        func.coalesce(func.sum(WbRealizationReport.quantity), 0).label("returns_units"),
    ).where(
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date,
        WbRealizationReport.supplier_oper_name == "Возврат",
    )
    return (await session.execute(_scope(query, user_id, scope))).one()


async def get_chart_data(session: AsyncSession, user_id: UUID, start_date: date, end_date: date, scope: DashboardAccountScope) -> list[dict[str, Any]]:
    query = (
        select(
            WbRealizationReport.rr_dt.label("date"),
            func.sum(WbRealizationReport.retail_amount).label("sales_amount"),
            func.sum(WbRealizationReport.quantity).label("sales_units"),
        )
        .where(
            WbRealizationReport.rr_dt >= start_date,
            WbRealizationReport.rr_dt <= end_date,
            WbRealizationReport.supplier_oper_name == "Продажа",
        )
        .group_by(WbRealizationReport.rr_dt)
        .order_by(WbRealizationReport.rr_dt)
    )
    rows = (await session.execute(_scope(query, user_id, scope))).all()
    return [{"date": row.date.isoformat(), "sales_amount": float(row.sales_amount or 0), "sales_units": int(row.sales_units or 0)} for row in rows]


async def get_warehouse_data(session: AsyncSession, user_id: UUID, scope: DashboardAccountScope) -> list[dict[str, Any]]:
    query = (
        select(
            WbRealizationReport.office_name.label("warehouse"),
            func.sum(WbRealizationReport.quantity).label("quantity"),
            func.sum(WbRealizationReport.retail_amount).label("amount"),
        )
        .where(WbRealizationReport.office_name.is_not(None))
        .group_by(WbRealizationReport.office_name)
        .order_by(func.sum(WbRealizationReport.retail_amount).desc())
    )
    rows = (await session.execute(_scope(query, user_id, scope))).all()
    return [{"warehouse": row.warehouse or "Не указан", "quantity": int(row.quantity or 0), "amount": float(row.amount or 0)} for row in rows]


async def get_abc_analysis(session: AsyncSession, user_id: UUID, start_date: date, end_date: date, scope: DashboardAccountScope) -> list[dict[str, Any]]:
    total_query = select(func.coalesce(func.sum(WbRealizationReport.retail_amount), 0)).where(
        WbRealizationReport.rr_dt >= start_date,
        WbRealizationReport.rr_dt <= end_date,
        WbRealizationReport.supplier_oper_name == "Продажа",
    )
    total_amount = float((await session.execute(_scope(total_query, user_id, scope))).scalar() or 0)
    query = (
        select(
            WbRealizationReport.nm_id.label("nm_id"),
            WbRealizationReport.brand_name.label("brand"),
            WbRealizationReport.sa_name.label("article"),
            func.sum(WbRealizationReport.retail_amount).label("sales_amount"),
            func.sum(WbRealizationReport.quantity).label("sales_units"),
        )
        .where(
            WbRealizationReport.rr_dt >= start_date,
            WbRealizationReport.rr_dt <= end_date,
            WbRealizationReport.supplier_oper_name == "Продажа",
        )
        .group_by(WbRealizationReport.nm_id, WbRealizationReport.brand_name, WbRealizationReport.sa_name)
        .order_by(func.sum(WbRealizationReport.retail_amount).desc())
    )
    rows = (await session.execute(_scope(query, user_id, scope))).all()
    result = []
    cumulative = 0.0
    for row in rows:
        amount = float(row.sales_amount or 0)
        percent = amount / total_amount * 100 if total_amount else 0.0
        cumulative += percent
        result.append({
            "nm_id": int(row.nm_id or 0),
            "brand": row.brand or "Не указан",
            "article": row.article or "Не указан",
            "sales_amount": amount,
            "sales_units": int(row.sales_units or 0),
            "percent": round(percent, 2),
            "category": "A" if cumulative <= 80 else ("B" if cumulative <= 95 else "C"),
        })
    return result


async def get_category_data(session: AsyncSession, user_id: UUID, start_date: date, end_date: date, scope: DashboardAccountScope) -> list[dict[str, Any]]:
    query = (
        select(
            WbRealizationReport.subject_name.label("category"),
            func.sum(WbRealizationReport.retail_amount).label("sales_amount"),
            func.sum(WbRealizationReport.quantity).label("sales_units"),
        )
        .where(
            WbRealizationReport.rr_dt >= start_date,
            WbRealizationReport.rr_dt <= end_date,
            WbRealizationReport.supplier_oper_name == "Продажа",
            WbRealizationReport.subject_name.is_not(None),
        )
        .group_by(WbRealizationReport.subject_name)
        .order_by(func.sum(WbRealizationReport.retail_amount).desc())
    )
    rows = (await session.execute(_scope(query, user_id, scope))).all()
    return [{"category": row.category or "Не указана", "sales_amount": float(row.sales_amount or 0), "sales_units": int(row.sales_units or 0)} for row in rows]


async def get_size_chart(session: AsyncSession, user_id: UUID, start_date: date, end_date: date, scope: DashboardAccountScope) -> list[dict[str, Any]]:
    query = (
        select(
            WbRealizationReport.ts_name.label("size"),
            func.sum(WbRealizationReport.retail_amount).label("sales_amount"),
            func.sum(WbRealizationReport.quantity).label("sales_units"),
        )
        .where(
            WbRealizationReport.rr_dt >= start_date,
            WbRealizationReport.rr_dt <= end_date,
            WbRealizationReport.supplier_oper_name == "Продажа",
            WbRealizationReport.ts_name.is_not(None),
        )
        .group_by(WbRealizationReport.ts_name)
        .order_by(func.sum(WbRealizationReport.retail_amount).desc())
    )
    rows = (await session.execute(_scope(query, user_id, scope))).all()
    return [{"size": row.size or "Не указан", "sales_amount": float(row.sales_amount or 0), "sales_units": int(row.sales_units or 0)} for row in rows]
