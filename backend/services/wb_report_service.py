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
        "rr_dt": parse_dt_safe(pick(item, "rrDt", "rr_dt")),
        "order_dt": parse_dt_safe(pick(item, "orderDt", "order_dt")),
        "sale_dt": parse_dt_safe(pick(item, "saleDt", "sale_dt")),
        "create_dt": parse_dt_safe(pick(item, "createDt", "create_dt")),

        # ids
        "nm_id": to_int(pick(item, "nmId", "nm_id")),
        "rrd_id": to_int(pick(item, "rrdId", "rrd_id")),
        "gi_id": to_int(pick(item, "giId", "gi_id")),  # Номер поставки
        "shk_id": to_int(pick(item, "shkId", "shk_id")),  # Штрих-код
        "srid": to_str(pick(item, "srid", "SRID")),
        "realization_report_id": to_int(pick(item, "realizationreportId", "realizationReportId")),  # Номер отчета

        # operation
        "supplier_oper_name": to_str(pick(item, "supplierOperName", "sellerOperName")),
        "doc_type_name": to_str(pick(item, "docTypeName", "docTypeName")),  # Тип документа

        # product info
        "subject_name": to_str(pick(item, "subjectName", "subjectName")),  # Предмет
        "brand_name": to_str(pick(item, "brandName", "brandName")),  # Бренд
        "sa_name": to_str(pick(item, "saName", "saName")),  # Артикул продавца
        "ts_name": to_str(pick(item, "tsName", "tsName")),  # Размер
        "barcode": to_str(pick(item, "barcode", "Barcode")),  # Баркод
        "title": to_str(pick(item, "title", "Title")),  # Название товара (новое поле)

        # warehouse/logistics
        "office_name": to_str(pick(item, "officeName", "officeName")),  # Склад
        "gi_box_type_name": to_str(pick(item, "giBoxTypeName", "giBoxTypeName")),  # Тип коробов
        "ppvz_office_id": to_int(pick(item, "ppvzOfficeId", "ppvzOfficeId")),  # Номер офиса
        "ppvz_office_name": to_str(pick(item, "ppvzOfficeName", "ppvzOfficeName")),  # Наименование офиса доставки

        # facts
        "quantity": to_int(pick(item, "quantity", "Quantity")),
        "retail_price": to_decimal(pick(item, "retailPrice", "retailPrice")),  # Цена розничная
        "retail_amount": to_decimal(pick(item, "retailAmount", "retailAmount")),  # Сумма продаж
        "retail_price_with_disc_rub": to_decimal(pick(item, "retailPriceWithdiscRub", "retailPriceWithdiscRub")),  # Цена с учетом скидки

        # discounts and commissions
        "sale_percent": to_decimal(pick(item, "salePercent", "salePercent")),  # Согласованная скидка
        "commission_percent": to_decimal(pick(item, "commissionPercent", "commissionPercent")),  # Процент комиссии
        "product_discount_for_report": to_decimal(pick(item, "productDiscountForReport", "productDiscountForReport")),  # Продуктовый дисконт
        "ppvz_spp_prc": to_decimal(pick(item, "ppvzSppPrc", "ppvzSppPrc")),  # Скидка постоянного покупателя

        # KVV (комиссия за выдачу и возврат)
        "ppvz_kvw_prc_base": to_decimal(pick(item, "ppvzKvwPrcBase", "ppvzKvwPrcBase")),  # Размер КВВ без НДС
        "ppvz_kvw_prc": to_decimal(pick(item, "ppvzKvwPrc", "ppvzKvwPrc")),  # Итоговый КВВ без НДС
        "sup_rating_prc_up": to_decimal(pick(item, "supRatingPrcUp", "supRatingPrcUp")),  # Снижение КВВ из-за рейтинга
        "is_kgvp_v2": to_decimal(pick(item, "isKgvpV2", "isKgvpV2")),  # Снижение КВВ из-за акции

        # financial
        "ppvz_for_pay": to_decimal(pick(item, "ppvzForPay", "forPay")),  # К перечислению продавцу (теперь string!)
        "ppvz_sales_commission": to_decimal(pick(item, "ppvzSalesCommission", "ppvzSalesCommission")),  # Вознаграждение с продаж
        "ppvz_reward": to_decimal(pick(item, "ppvzReward", "ppvzReward")),  # Возмещение за выдачу и возврат товаров
        "ppvz_vw": to_decimal(pick(item, "ppvzVw", "ppvzVw")),  # Вознаграждение WB без НДС
        "ppvz_vw_nds": to_decimal(pick(item, "ppvzVwNds", "ppvzVwNds")),  # НДС с вознаграждения WB

        # logistics costs
        "delivery_amount": to_int(pick(item, "deliveryAmount", "deliveryAmount")),  # Количество доставок
        "return_amount": to_int(pick(item, "returnAmount", "returnAmount")),  # Количество возвратов
        "delivery_rub": to_decimal(pick(item, "deliveryRub", "deliveryRub")),  # Стоимость логистики
        "return_rub": to_decimal(pick(item, "returnRub", "returnRub")),  # Стоимость возврата
        "rebill_logistic_cost": to_decimal(pick(item, "rebillLogisticCost", "rebillLogisticCost")),  # Возмещение издержек по перевозке
        "rebill_logistic_org": to_str(pick(item, "rebillLogisticOrg", "rebillLogisticOrg")),  # Организатор перевозки
        "storage_fee": to_decimal(pick(item, "storageFee", "storageFee")),  # Стоимость хранения
        "acceptance": to_decimal(pick(item, "acceptance", "acceptance")),  # Стоимость платной приемки

        # payments and penalties
        "penalty": to_decimal(pick(item, "penalty", "penalty")),  # Штрафы
        "additional_payment": to_decimal(pick(item, "additionalPayment", "additionalPayment")),  # Доплаты
        "deduction": to_decimal(pick(item, "deduction", "deduction")),  # Прочие удержания
        "acquiring_fee": to_decimal(pick(item, "acquiringFee", "acquiringFee")),  # Издержки по эквайрингу
        "acquiring_bank": to_str(pick(item, "acquiringBank", "acquiringBank")),  # Банк эквайер

        # promo and marketing
        "supplier_promo": to_str(pick(item, "supplierPromo", "supplierPromo")),  # Промокод
        "order_uid": to_str(pick(item, "orderUid", "orderUid")),  # Уникальный идентификатор заказа
        "kiz": to_str(pick(item, "kiz", "kiz")),  # Код маркировки
        "declaration_number": to_str(pick(item, "declarationNumber", "declarationNumber")),  # Номер таможенной декларации

        # partner info (ppvzSupplierId больше не поддерживается!)
        "ppvz_supplier_id": to_int(pick(item, "ppvzSupplierId", "ppvzSupplierId")),  # Номер партнера (может быть null)
        "ppvz_supplier_name": to_str(pick(item, "ppvzSupplierName", "ppvzSupplierName")),  # Партнер
        "ppvz_inn": to_str(pick(item, "ppvzInn", "ppvzInn")),  # ИНН партнера

        # report meta
        "currency_name": to_str(pick(item, "currencyName", "currencyName")),  # Валюта отчета
        "report_type": to_int(pick(item, "reportType", "reportType")),  # Тип отчета
        "trbx_id": to_str(pick(item, "trbxId", "trbxId")),  # Месяц

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