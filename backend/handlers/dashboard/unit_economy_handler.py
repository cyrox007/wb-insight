import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Dict, Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from services.user_service import get_user_tax_rate
from services.wb_report_service import get_reports_with_costs
from services.dashboard.unit_economy_service import UnitEconomyMetricsService
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix='/dashboard/unity', tags=['Unit'])

@router.get('/', dependencies=[Depends(auth_middle)])
async def get_unit_economy(
    request: Request, 
    db_session: AsyncSession = Depends(get_db_session),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
):
    end_date = end_date if end_date is not None else datetime.now(timezone.utc).date()
    start_date = start_date if start_date is not None else end_date - timedelta(days=30)
    current_user = request.state.user

    reports_with_costs = await get_reports_with_costs(
        db_session, 
        UUID(current_user['sub']), 
        start_date, 
        end_date
    )

    if len(reports_with_costs) == 0:
        return response_error(
            code="NOT_DATA",
            message="Данные еще не сихронизированы"
        )
    
    report_data = []
    for report, cost in reports_with_costs:
        report_data.append({
            
            "rr_dt": report.rr_dt,              # Дата отчёта (ключевое поле для агрегации)
            "order_dt": report.order_dt,            # Дата заказа
            "sale_dt": report.sale_dt,            # Дата продажи (дублируется с rr_dt)
            "date_from": report.date_from,   # Начало периода отчёта
            "date_to": report.date_to,      # Конец периода отчёта
            "create_dt": report.create_dt,  # Дата создания отчёта
            #"operation_dt": report,      # Дата операции (добавить, если нет в модели)

            # ========== Идентификаторы ==========
            "nm_id": report.nm_id,                # nmID товара
            "rrd_id": report.rrd_id,             # ID строки отчёта (уникальный)
            "gi_id": report.gi_id,            # Номер поставки
            "shk_id": report.shk_id,                # Штрих-код (shkId)
            "srid": report.srid,  # SRID
            "realization_report_id": report.realization_report_id,  # Номер отчёта

            # ========== Типы операций и документов ==========
            "supplier_oper_name": report.supplier_oper_name,  # Тип операции Обоснование оплаты (Продажа/Логистика/Возврат)
            "doc_type_name": report.doc_type_name,     # Тип документа

            # ========== Товарные данные ==========
            "subject_name": report.subject_name,            # Предмет (категория)
            "brand_name": report.brand_name,                # Бренд
            "sa_name": report.sa_name,        # Артикул продавца
            "ts_name": report.ts_name,                  # Размер
            "barcode": report.barcode,                  # Баркод (строковый)
            "office_name": report.office_name,               # Склад хранения
            "gi_box_type_name": report.gi_box_type_name,    # Тип коробов (Микс и т.д.)
            "ppvz_office_name": report.ppvz_office_name,  # Офис доставки
            "ppvz_office_id": report.ppvz_office_id,      # ID офиса доставки
            "kiz": report.kiz,              # Код маркировки (КИЗ)
            "declaration_number": report.declaration_number,  # ГТД

            # ========== Финансовые данные (количество и цены) ==========
            "quantity": report.quantity,             # Количество единиц
            "delivery_amount": report.delivery_amount,  # Кол-во доставок
            "return_amount": report.return_amount,   # Кол-во возвратов
            "retail_price": report.retail_price,     # Розничная цена
            "retail_amount": report.retail_amount,      # Сумма продажи/возврата
            "retail_price_with_disc_rub": report.retail_price_with_disc_rub,  # Цена со скидкой
            "sale_percent": report.sale_percent,  # Скидка согласованная (%)
            "commission_percent": report.commission_percent,  # % комиссии WB
            "product_discount_for_report": report.product_discount_for_report,  # Дисконт на товар
            "ppvz_spp_prc": report.ppvz_spp_prc,  # Скидка покупателя (SPP)

            # ========== KVV и комиссии ==========
            "ppvz_kvw_prc_base": report.ppvz_kvw_prc_base,  # Базовый размер КВВ
            "ppvz_kvw_prc": report.ppvz_kvw_prc,     # Итоговый КВВ
            "sup_rating_prc_up": report.sup_rating_prc_up,  # Корректировка за рейтинг
            "is_kgvp_v2": report.is_kgvp_v2,   # Корректировка за акцию
            "ppvz_sales_commission": report.ppvz_sales_commission,  # Комиссия с продаж
            "ppvz_vw": report.ppvz_vw,      # Вознаграждение WB
            "ppvz_vw_nds": report.ppvz_vw_nds,    # НДС с вознаграждения

            # ========== Логистика ==========
            "delivery_rub": report.delivery_rub,   # Стоимость доставки
            "return_rub": report.return_rub,      # Стоимость возврата (если есть)
            "rebill_logistic_cost": report.rebill_logistic_cost,  # Компенсация логистики
            "rebill_logistic_org": report.rebill_logistic_org,  # Организатор перевозки
            "storage_fee": report.storage_fee,     # Плата за хранение
            "acceptance": report.acceptance,  # Платная приёмка

            # ========== Платежи и удержания ==========
            "ppvz_for_pay": report.ppvz_for_pay,  # Сумма к перечислению
            "ppvz_reward": report.ppvz_reward,  # Компенсация выдачи/возврата
            "penalty": report.penalty,                    # Штрафы
            "additional_payment": report.additional_payment,        # Доплаты
            "deduction": report.deduction,        # Прочие удержания
            "acquiring_fee": report.acquiring_fee,  # Эквайринг
            "acquiring_bank": report.acquiring_bank,       # Банк эквайера

            # ========== Промо и маркетинг ==========
            "supplier_promo": report.supplier_promo,           # Промокод
            "order_uid": report.order_uid,  # UUID заказа

            # ========== Информация о партнере ==========
            "ppvz_supplier_id": report.ppvz_supplier_id,   # ID партнёра
            "ppvz_supplier_name": report.ppvz_supplier_name,        # Название партнёра
            "ppvz_inn": report.ppvz_inn,             # ИНН партнёра

            # ========== Мета отчёта ==========
            "currency_name": report.currency_name,       # Валюта (RUB и т.д.)
            "report_type": report.report_type,            # Тип отчёта
            "trbx_id": report.trbx_id,                    # Месяц (или другой идентификатор)

            "product_cost": cost.cost_price if cost else 0 # Себестоимость товара
        })

    df = pd.DataFrame(report_data)

    # Получаем налоговую ставку пользователя
    tax_rate = await get_user_tax_rate(db_session, UUID(current_user['sub']))

    # Создаем сервис и рассчитываем все метрики
    metrics_service = UnitEconomyMetricsService(tax_rate=tax_rate)
    result_df = metrics_service.calculate_all_metrics(df)
    
    # Формируем ответ с таблицей и сводными данными
    return _format_response(result_df)


def _format_response(df: pd.DataFrame) -> Dict[str, Any]:
    """Форматирует DataFrame в ответ API с таблицей и сводными данными"""
    
    # Первая строка - это "ИТОГО", остальные - по артикулам
    if len(df) == 0:
        return response_success(data={})
    
    summary_row = df.iloc[0].to_dict()
    articles_df = df.iloc[1:].copy()
    
    # Конвертируем таблицу в список словарей
    table_data = articles_df.replace([np.nan], [None]).to_dict(orient='records')
    
    # Формируем сводные данные из первой строки
    summary_data = {
        'sales_with_spp': summary_row.get('sales_with_spp', 0),
        'wb_commission_percent': summary_row.get('wb_commission_percent', 0),
        'wb_commission_amount': summary_row.get('sales_with_spp', 0) * summary_row.get('wb_commission_percent', 0) / 100,
        'to_pay_seller': summary_row.get('to_pay_seller', 0),
        'logistics': summary_row.get('logistics_total', 0),
        'storage': summary_row.get('storage', 0),
        'other_deductions': summary_row.get('other_deductions', 0),
        'fines': summary_row.get('fines', 0),
        'paid_acceptance': summary_row.get('paid_acceptance', 0),
        'total_to_pay': summary_row.get('total_to_pay', 0),
        
        'avg_sale_price': summary_row.get('avg_sale_price', 0),
        'tax': summary_row.get('tax', 0),
        'other_expenses': 0,  # Заглушка, пока нет данных
        'drr': summary_row.get('drr', 0),
        'cost_price': summary_row.get('cost_price_total', 0),
        'marginality': summary_row.get('margin', 0),
        'profitability': summary_row.get('profitability', 0),
        'profit_per_unit': summary_row.get('profit_per_unit', 0),
        'profit': summary_row.get('profit', 0),
    }
    
    # Данные для графика по дням (нужно агрегировать исходные данные)
    # Пока заглушка - нужно будет доработать при наличии daily_data
    daily_data = []
    
    return response_success(data={
        'summary': summary_data,
        'table': table_data,
        'daily_data': daily_data
    })