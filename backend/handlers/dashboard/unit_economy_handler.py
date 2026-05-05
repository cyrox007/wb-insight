import pandas as pd
import numpy as np
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from services.user_service import get_user_tax_rate
from services.wb_report_service import get_reports_with_costs
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

            "product_cost": cost.cost_price # Себестоимость товара
        })

    df = pd.DataFrame(report_data)

    # Получаем налоговую ставку пользователя
    tax_rate = await get_user_tax_rate(db_session, UUID(current_user['sub']))

    # Рассчитываем все метрики
    result_df = calculate_all_metrics(df, tax_rate)

    return response_success(report=result_df)

def calculate_all_metrics(df: pd.DataFrame, tax_rate: float = 0.2) -> pd.DataFrame:
    # Валидация входных данных
    if df.empty:
        return pd.DataFrame()
    
    required_columns = [
        'nm_id', 'supplier_oper_name', 'doc_type_name', 'quantity',
        'retail_price_with_disc_rub', 'retail_amount', 'delivery_amount',
        'ppvz_kvw_prc_base', 'ppvz_sales_commission', 'ppvz_for_pay',
        'delivery_rub', 'acquiring_fee', 'storage_fee', 'penalty',
        'deduction', 'acceptance', 'product_cost', 'ppvz_vw_nds'
    ]

    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Отсутствуют необходимые колонки: {missing_columns}")
    
    # Маски для продаж и возвратов
    is_sale = (
        (df['supplier_oper_name'] == 'Продажа') &
        (df['doc_type_name'] == 'Продажа')
    )
    is_return = (
        df['supplier_oper_name'] == 'Возврат'
    )

    # ========== 1. Базовые агрегации ==========
    df['cost_total'] = df['product_cost'] * df['quantity']
    # Продажи
    sales_data = df[is_sale].groupby('nm_id').agg(
        {
            'retail_price_with_disc_rub': 'sum',  # Сумма продаж без СПП
            'retail_amount': 'sum',                 # Сумма продаж с СПП
            'quantity': 'sum',                     # Количество продаж
            'delivery_amount': 'sum',              # Количество доставок
            'ppvz_kvw_prc_base': 'mean',           # Размер КВВ без НДС (%)
            'ppvz_sales_commission': 'sum',        # Комиссия с продаж
            'ppvz_sales_commission': 'sum',        # Вознаграждение с продаж
            'ppvz_for_pay': 'sum',                 # К перечислению
            'delivery_rub': 'sum',                 # Логистика
            'acquiring_fee': 'sum',                # Эквайринг
            'storage_fee': 'sum',                  # Хранение
            'penalty': 'sum',                      # Штрафы
            'deduction': 'sum',                    # Прочие удержания
            'acceptance': 'sum',                   # Платная приемка
            'cost_total': 'sum',                   # Себестоимость (суммируем, потом поделим)
            'ppvz_vw_nds': 'sum'                   # НДС с вознаграждения
        }
    ).fillna(0)

    # Возвраты
    returns_data = df[is_return].groupby('nm_id').agg(
        {
            'retail_price_with_disc_rub': 'sum',  # Возвраты без СПП
            'retail_price': 'sum',                 # Возвраты с СПП
            'quantity': 'sum',                     # Количество возвратов
            'retail_amount': 'sum',                # Сумма возвратов
            'delivery_rub': 'sum',                 # Логистика возвратов
            'ppvz_for_pay': 'sum',                 # Коррекции возвратов
            'delivery_amount': 'sum'               # Количество возвратных доставок
        }
    ).fillna(0)

    # Переименовываем колонки возвратов
    returns_data.columns = [f'return_{col}' if col != 'nm_id' else col 
                           for col in returns_data.columns]
    
    # ========== 2. Объединяем продажи и возвраты ==========
    result = sales_data.join(returns_data, how='outer').fillna(0)
    result = result.reset_index()

    # ========== 3. Расчёт основных метрик ==========
    
    # 📦 Объёмы
    result['sales_quantity'] = result['quantity']
    result['returns_quantity'] = result['return_quantity']
    result['net_quantity'] = result['sales_quantity'] - result['returns_quantity']
    result['delivery_quantity'] = result['delivery_amount']
    result['return_delivery_quantity'] = result['return_delivery_amount']
    result['return_delivery_quantity'] = result.get('return_delivery_amount', 0)
    result['net_delivery'] = result['delivery_quantity'] - result['return_delivery_quantity']
    result['buyout_percent'] = np.where(
        result['delivery_quantity'] > 0,
        result['sales_quantity'] / result['delivery_quantity'] * 100,
        0
    )
    
    # 💰 Выручка / продажи
    result['sales_without_spp'] = result['retail_price_with_disc_rub'] - result['return_retail_price_with_disc_rub']
    result['sales_with_spp'] = result['retail_amount'] - result['return_retail_amount']
    result['returns_amount'] = result['return_retail_amount']
    
    # 💳 Комиссии и эквайринг
    result['ppvz_kvw_prc_base'] = result['ppvz_kvw_prc_base']  # Средний % КВВ
    result['acquiring_fee'] = result['acquiring_fee']
    
    # 💸 Выплаты
    result['ppvz_for_pay'] = result['ppvz_for_pay'] - result.get('return_ppvz_for_pay', 0)
    
    # 🚚 Логистика
    result['delivery_rub'] = result['delivery_rub'] - result.get('return_delivery_rub', 0)
    result['logistics_per_delivery'] = np.where(
        result['delivery_quantity'] > 0,
        result['delivery_rub'] / result['delivery_quantity'],
        0
    )
    result['logistics_per_sale'] = np.where(
        result['sales_quantity'] > 0,
        result['delivery_rub'] / result['sales_quantity'],
        0
    )
    
    # 🏬 Хранение
    result['storage_fee'] = result['storage_fee']
    
    # ⚠️ Прочие расходы
    result['penalty'] = result['penalty']
    result['deduction'] = result['deduction']
    result['acceptance'] = result['acceptance']
    
    # 🧾 Налоги и реклама
    result['tax'] = result['sales_with_spp'] * tax_rate
    # Расходы на РК нужно будет добавить отдельно из другого источника
    result['advertising_cost'] = 0  # TODO: из рекламной статистики
    result['drr'] = np.where(
        result['sales_with_spp'] > 0,
        result['advertising_cost'] / result['sales_with_spp'] * 100,
        0
    )
    
    # 💰 Себестоимость и расходы
    result['product_cost'] = result['cost_total']
    result['avg_product_cost'] = np.where(
        result['net_quantity'] > 0,
        result['product_cost'] / result['net_quantity'],
        0
    )
    
    # 💵 Итоговые расчёты
    result['total_costs'] = (
        result['product_cost'] +           # Себестоимость
        result['delivery_rub'] +           # Логистика
        result['storage_fee'] +            # Хранение
        result['acquiring_fee'] +          # Эквайринг
        result['penalty'] +                # Штрафы
        result['deduction'] +              # Прочие удержания
        result['acceptance'] +             # Платная приемка
        result['tax'] +                    # Налог
        result['advertising_cost'] +       # Реклама
        result['ppvz_sales_commission'] +  # Комиссия WB с продаж
        result['ppvz_vw_nds']              # НДС с вознаграждения WB
    )
    
    result['profit'] = result['sales_without_spp'] - result['total_costs']
    result['profit_per_unit'] = np.where(
        result['sales_quantity'] > 0,
        result['profit'] / result['sales_quantity'],
        0
    )
    result['margin'] = np.where(
        result['sales_without_spp'] > 0,
        (result['sales_without_spp'] - result['total_costs']) / result['sales_without_spp'] * 100,
        0
    )
    result['roi'] = np.where(
        result['total_costs'] > 0,
        result['profit'] / result['total_costs'] * 100,
        0
    )
    result['avg_selling_price'] = np.where(
        result['sales_quantity'] > 0,
        result['sales_without_spp'] / result['sales_quantity'],
        0
    )
    
    # Определяем маски для разных типов коррекций
    is_correction_acquiring = df['supplier_oper_name'] == 'Корректировка эквайринга'

    is_correction_sales = df['supplier_oper_name'] == 'Коррекция продаж'
    is_correction_sales_sale = is_correction_sales & (df['doc_type_name'] == 'Продажа')
    is_correction_sales_return = is_correction_sales & (df['doc_type_name'] == 'Возврат')

    is_correction_returns = df['supplier_oper_name'] == 'Коррекция возвратов'

    is_compensation = df['supplier_oper_name'] == 'Компенсация ущерба'

    # Агрегируем коррекции
    correction_acquiring_data = df[is_correction_acquiring].groupby('nm_id')['ppvz_for_pay'].sum().fillna(0)
    correction_sales_sale_data = df[is_correction_sales_sale].groupby('nm_id')['ppvz_for_pay'].sum().fillna(0)
    correction_sales_return_data = df[is_correction_sales_return].groupby('nm_id')['ppvz_for_pay'].sum().fillna(0)
    correction_returns_data = df[is_correction_returns].groupby('nm_id')['ppvz_for_pay'].sum().fillna(0)
    compensation_data = df[is_compensation].groupby('nm_id')['ppvz_for_pay'].sum().fillna(0)

    # Добавляем в результат
    result['correction_acquiring'] = result['nm_id'].map(correction_acquiring_data).fillna(0)
    result['correction_sales_sale'] = result['nm_id'].map(correction_sales_sale_data).fillna(0)
    result['correction_sales_return'] = result['nm_id'].map(correction_sales_return_data).fillna(0)
    result['correction_returns'] = result['nm_id'].map(correction_returns_data).fillna(0)
    result['compensation'] = result['nm_id'].map(compensation_data).fillna(0)
    
    # ========== 4. Выбор финальных колонок ==========
    final_columns = [
        'nm_id',  # Артикул WB
        
        # Выручка / продажи
        'sales_without_spp',  # Сумма продаж без СПП
        'sales_with_spp',     # Сумма продаж с СПП
        'returns_amount',     # Сумма возвратов
        
        # Объёмы
        'sales_quantity',     # Количество продаж
        'delivery_quantity',  # Количество доставок
        'returns_quantity',   # Возвратов
        'buyout_percent',     # Процент выкупа
        'net_quantity',       # Чистое количество
        
        # Комиссии и эквайринг
        'ppvz_kvw_prc_base',  # Размер КВВ без НДС, %
        'acquiring_fee',      # Эквайринг
        
        # Выплаты
        'ppvz_for_pay',       # К перечислению
        
        # Логистика
        'delivery_rub',       # Логистика
        'logistics_per_delivery',  # Логистика на 1 доставку
        'logistics_per_sale',      # Логистика на 1 продажу
        
        # Хранение
        'storage_fee',        # Хранение
        
        # Прочие расходы
        'penalty',            # Штраф
        'deduction',          # Прочие удержания
        'acceptance',         # Платная приемка
        
        # Налоги и реклама
        'tax',                # Налог
        'advertising_cost',   # Расходы на РК
        'drr',                # ДРР
        
        # Себестоимость и прибыль
        'product_cost',       # Себестоимость общая
        'avg_product_cost',   # Себестоимость на единицу
        'total_costs',        # Все расходы
        'profit',             # Прибыль
        'profit_per_unit',    # Прибыль на 1 единицу
        'margin',             # Маржинальность %
        'roi',                # Рентабельность %
        'avg_selling_price',  # Средняя стоимость продажи
        
        # Коррекции
        'correction_acquiring',     # Коррекция эквайринга
        'correction_sales_sale',    # Коррекция продаж (Продажа)
        'correction_sales_return',  # Коррекция продаж (возврат)
        'correction_returns',       # Коррекция возвратов
        'compensation'              # Компенсация
    ]
    
    # Оставляем только существующие колонки
    final_columns = [col for col in final_columns if col in result.columns]
    result = result[final_columns]
    
    # Округляем числовые колонки
    numeric_cols = result.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        if col != 'nm_id':
            result[col] = result[col].round(2)
    return result