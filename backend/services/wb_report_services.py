from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.wb_report import WbRealizationReport

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
    return result.fetchone()