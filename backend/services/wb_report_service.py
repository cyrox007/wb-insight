from datetime import date
from uuid import UUID

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
    stats = result.fetchone()
    print(stats)
    return stats

from datetime import datetime
from sqlalchemy.dialects.postgresql import insert

from models.wb_report import WbRealizationReport


async def save_realization(
    session: AsyncSession,
    user_id: UUID,
    data: list[dict],
):
    if not data:
        return

    values = []

    for item in data:
        values.append({
            "user_id": user_id,

            # даты
            "rr_dt": item["rr_dt"],
            "order_dt": item.get("order_dt"),
            "sale_dt": item.get("sale_dt"),
            "date_from": item.get("date_from"),
            "date_to": item.get("date_to"),
            "create_dt": item.get("create_dt"),

            # идентификаторы
            "nm_id": item["nm_id"],
            "rrd_id": item["rrd_id"],
            "realizationreport_id": item["realizationreport_id"],
            "gi_id": item.get("gi_id"),
            "srid": item.get("srid"),
            "order_uid": item.get("order_uid"),
            "assembly_id": item.get("assembly_id"),
            "shk_id": item.get("shk_id"),

            # типы
            "supplier_oper_name": item["supplier_oper_name"],
            "doc_type_name": item.get("doc_type_name"),

            # товар
            "subject_name": item.get("subject_name"),
            "brand_name": item.get("brand_name"),
            "sa_name": item.get("sa_name"),
            "ts_name": item.get("ts_name"),
            "barcode": item.get("barcode"),
            "kiz": item.get("kiz"),
            "office_name": item.get("office_name"),

            # деньги
            "retail_amount": item.get("retail_amount", 0),
            "retail_price": item.get("retail_price"),
            "retail_price_withdisc_rub": item.get("retail_price_withdisc_rub"),
            "quantity": item.get("quantity", 0),
            "delivery_amount": item.get("delivery_amount"),
            "return_amount": item.get("return_amount"),
            "ppvz_sales_commission": item.get("ppvz_sales_commission", 0),
            "delivery_rub": item.get("delivery_rub", 0),
            "return_rub": item.get("return_rub"),
            "penalty": item.get("penalty", 0),
            "additional_payment": item.get("additional_payment", 0),
            "storage_fee": item.get("storage_fee", 0),
            "ppvz_for_pay": item.get("ppvz_for_pay", 0),
            "ppvz_reward": item.get("ppvz_reward"),
            "acquiring_fee": item.get("acquiring_fee"),

            # проценты
            "sale_percent": item.get("sale_percent"),
            "commission_percent": item.get("commission_percent"),
            "ppvz_spp_prc": item.get("ppvz_spp_prc"),
            "ppvz_kvw_prc_base": item.get("ppvz_kvw_prc_base"),
            "ppvz_kvw_prc": item.get("ppvz_kvw_prc"),
            "ppvz_vw": item.get("ppvz_vw"),
            "ppvz_vw_nds": item.get("ppvz_vw_nds"),

            "created_at": datetime.utcnow(),
        })

    stmt = insert(WbRealizationReport).values(values)

    # ❗ ключевая часть — НЕ обновляем, просто игнорим дубли
    stmt = stmt.on_conflict_do_nothing(
        index_elements=["rrd_id"]
    )

    await session.execute(stmt)