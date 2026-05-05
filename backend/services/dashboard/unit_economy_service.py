"""
Сервис для расчета метрик юнит-экономики.
Декомпозиция логики из unit_economy_handler.py
"""

import pandas as pd
import numpy as np
from typing import Tuple


class UnitEconomyMetricsService:
    """Сервис для расчета всех метрик юнит-экономики"""
    
    def __init__(self, tax_rate: float = 0.2):
        self.tax_rate = tax_rate
    
    def calculate_all_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Рассчитывает все метрики юнит-экономики на основе данных отчета WB
        
        Args:
            df: DataFrame с данными отчетов WB
            
        Returns:
            DataFrame с агрегированными метриками по артикулам
        """
        if df.empty:
            return pd.DataFrame()
        
        self._validate_columns(df)
        
        # Создаем маски для типов операций
        is_sale, is_return = self._create_operation_masks(df)
        
        # Агрегируем данные по продажам и возвратам
        sales_data = self._aggregate_sales(df, is_sale)
        returns_data = self._aggregate_returns(df, is_return)
        
        # Объединяем продажи и возвраты
        result = self._merge_sales_and_returns(sales_data, returns_data)
        
        # Рассчитываем основные метрики
        self._calculate_volume_metrics(result)
        self._calculate_revenue_metrics(result)
        self._calculate_commission_metrics(result)
        self._calculate_payout_metrics(result)
        self._calculate_logistics_metrics(result)
        self._calculate_storage_metrics(result)
        self._calculate_penalty_metrics(result)
        self._calculate_tax_and_advertising_metrics(result)
        self._calculate_cost_metrics(result)
        self._calculate_profitability_metrics(result)
        
        # Рассчитываем коррекции
        self._calculate_corrections(df, result)
        
        # Формируем финальный DataFrame
        result = self._select_final_columns(result)
        result = self._round_numeric_columns(result)
        
        # Добавляем итоговую строку (агрегация по всем артикулам)
        summary_row = self._create_summary_row(result)
        final_df = pd.concat([summary_row, result], ignore_index=True)
        
        return final_df
    
    def _validate_columns(self, df: pd.DataFrame) -> None:
        """Проверяет наличие необходимых колонок"""
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
    
    def _create_operation_masks(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Создает маски для фильтрации продаж и возвратов"""
        is_sale = (
            (df['supplier_oper_name'] == 'Продажа') &
            (df['doc_type_name'] == 'Продажа')
        )
        is_return = (df['supplier_oper_name'] == 'Возврат')
        return is_sale, is_return
    
    def _aggregate_sales(self, df: pd.DataFrame, is_sale: pd.Series) -> pd.DataFrame:
        """Агрегирует данные по продажам"""
        # Добавляем колонку общей себестоимости
        df['cost_total'] = df['product_cost'].fillna(0) * df['quantity']
        
        sales_data = df[is_sale].groupby('nm_id').agg(
            {
                'retail_price_with_disc_rub': 'sum',  # Сумма продаж без СПП
                'retail_amount': 'sum',                 # Сумма продаж с СПП
                'quantity': 'sum',                     # Количество продаж
                'delivery_amount': 'sum',              # Количество доставок
                'ppvz_kvw_prc_base': 'mean',           # Размер КВВ без НДС (%)
                'ppvz_sales_commission': 'sum',        # Комиссия с продаж
                'ppvz_for_pay': 'sum',                 # К перечислению
                'delivery_rub': 'sum',                 # Логистика
                'acquiring_fee': 'sum',                # Эквайринг
                'storage_fee': 'sum',                  # Хранение
                'penalty': 'sum',                      # Штрафы
                'deduction': 'sum',                    # Прочие удержания
                'acceptance': 'sum',                   # Платная приемка
                'cost_total': 'sum',                   # Себестоимость продаж
                'ppvz_vw_nds': 'sum'                   # НДС с вознаграждения
            }
        ).fillna(0)
        
        return sales_data
    
    def _aggregate_returns(self, df: pd.DataFrame, is_return: pd.Series) -> pd.DataFrame:
        """Агрегирует данные по возвратам"""
        returns_data = df[is_return].groupby('nm_id').agg(
            {
                'retail_price_with_disc_rub': 'sum',  # Возвраты без СПП
                'retail_amount': 'sum',                 # Сумма возвратов
                'quantity': 'sum',                     # Количество возвратов
                'delivery_rub': 'sum',                 # Логистика возвратов
                'ppvz_for_pay': 'sum',                 # Коррекции возвратов
                'delivery_amount': 'sum',              # Количество возвратных доставок
                'cost_total': 'sum'                    # Себестоимость возвратов
            }
        ).fillna(0)
        
        # Переименовываем колонки возвратов
        returns_data.columns = [f'return_{col}' for col in returns_data.columns]
        
        return returns_data
    
    def _merge_sales_and_returns(self, sales_data: pd.DataFrame, returns_data: pd.DataFrame) -> pd.DataFrame:
        """Объединяет данные по продажам и возвратам"""
        result = sales_data.join(returns_data, how='outer').fillna(0)
        result = result.reset_index()
        return result
    
    def _calculate_volume_metrics(self, result: pd.DataFrame) -> None:
        """Рассчитывает метрики объёмов"""
        result['sales_quantity'] = result['quantity']
        result['returns_quantity'] = result.get('return_quantity', 0)
        result['net_quantity'] = result['sales_quantity'] - result['returns_quantity']
        result['delivery_quantity'] = result['delivery_amount']
        result['return_delivery_quantity'] = result.get('return_delivery_amount', 0)
        
        # Процент выкупа
        result['buyout_percent'] = np.where(
            result['delivery_quantity'] > 0,
            result['sales_quantity'] / result['delivery_quantity'] * 100,
            0
        )
    
    def _calculate_revenue_metrics(self, result: pd.DataFrame) -> None:
        """Рассчитывает метрики выручки"""
        # Сумма продаж без СПП = Продажи без СПП - Возвраты без СПП
        result['sales_without_spp'] = (
            result['retail_price_with_disc_rub'] - 
            result.get('return_retail_price_with_disc_rub', 0)
        )
        
        # Сумма продаж с СПП = Продажи с СПП - Возвраты с СПП
        result['sales_with_spp'] = (
            result['retail_amount'] - 
            result.get('return_retail_amount', 0)
        )
        
        # Сумма возвратов
        result['returns_amount'] = result.get('return_retail_amount', 0)
    
    def _calculate_commission_metrics(self, result: pd.DataFrame) -> None:
        """Рассчитывает метрики комиссий и эквайринга"""
        result['ppvz_kvw_prc_base'] = result['ppvz_kvw_prc_base']
        result['acquiring_fee'] = result['acquiring_fee']
    
    def _calculate_payout_metrics(self, result: pd.DataFrame) -> None:
        """Рассчитывает метрики выплат"""
        # К перечислению = Продажи - Возвраты
        result['ppvz_for_pay'] = (
            result['ppvz_for_pay'] - 
            result.get('return_ppvz_for_pay', 0)
        )
    
    def _calculate_logistics_metrics(self, result: pd.DataFrame) -> None:
        """Рассчитывает метрики логистики"""
        # Логистика = Логистика продаж - Логистика возвратов
        result['delivery_rub'] = (
            result['delivery_rub'] - 
            result.get('return_delivery_rub', 0)
        )
        
        # Логистика на единицу от продажи
        result['logistics_per_sale'] = np.where(
            result['sales_quantity'] > 0,
            result['delivery_rub'] / result['sales_quantity'],
            0
        )
        
        # Логистика на единицу (от доставки)
        result['logistics_per_delivery'] = np.where(
            result['delivery_quantity'] > 0,
            result['delivery_rub'] / result['delivery_quantity'],
            0
        )
    
    def _calculate_storage_metrics(self, result: pd.DataFrame) -> None:
        """Рассчитывает метрики хранения"""
        result['storage_fee'] = result['storage_fee']
    
    def _calculate_penalty_metrics(self, result: pd.DataFrame) -> None:
        """Рассчитывает метрики штрафов и прочих расходов"""
        result['penalty'] = result['penalty']
        result['deduction'] = result['deduction']
        result['acceptance'] = result['acceptance']
    
    def _calculate_tax_and_advertising_metrics(self, result: pd.DataFrame) -> None:
        """Рассчитывает метрики налогов и рекламы"""
        # Налог = Сумма продаж с СПП * Ставка налога
        result['tax'] = result['sales_with_spp'] * self.tax_rate
        
        # Расходы на РК (пока заглушка)
        result['advertising_cost'] = 0  # TODO: из рекламной статистики
        
        # ДРР
        result['drr'] = np.where(
            result['sales_with_spp'] > 0,
            result['advertising_cost'] / result['sales_with_spp'] * 100,
            0
        )
    
    def _calculate_cost_metrics(self, result: pd.DataFrame) -> None:
        """Рассчитывает метрики себестоимости"""
        # Себестоимость = (Себестоимость продаж - Себестоимость возвратов)
        result['product_cost'] = (
            result['cost_total'] - 
            result.get('return_cost_total', 0)
        )
        
        # Средняя себестоимость на единицу
        result['avg_product_cost'] = np.where(
            result['net_quantity'] > 0,
            result['product_cost'] / result['net_quantity'],
            0
        )
    
    def _calculate_profitability_metrics(self, result: pd.DataFrame) -> None:
        """Рассчитывает итоговые метрики прибыли и рентабельности"""
        # Все расходы
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
        
        # Прибыль = Сумма продаж без СПП - Все расходы
        result['profit'] = result['sales_without_spp'] - result['total_costs']
        
        # Прибыль на единицу
        result['profit_per_unit'] = np.where(
            result['sales_quantity'] > 0,
            result['profit'] / result['sales_quantity'],
            0
        )
        
        # Маржинальность
        result['margin'] = np.where(
            result['sales_without_spp'] > 0,
            (result['sales_without_spp'] - result['total_costs']) / result['sales_without_spp'] * 100,
            0
        )
        
        # Рентабельность
        result['roi'] = np.where(
            result['total_costs'] > 0,
            result['profit'] / result['total_costs'] * 100,
            0
        )
        
        # Средняя стоимость продажи
        result['avg_selling_price'] = np.where(
            result['sales_quantity'] > 0,
            result['sales_without_spp'] / result['sales_quantity'],
            0
        )
    
    def _calculate_corrections(self, df: pd.DataFrame, result: pd.DataFrame) -> None:
        """Рассчитывает различные типы коррекций"""
        # Маски для коррекций
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
    
    def _select_final_columns(self, result: pd.DataFrame) -> pd.DataFrame:
        """Выбирает финальные колонки для вывода"""
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
        return result[final_columns]
    
    def _round_numeric_columns(self, result: pd.DataFrame) -> pd.DataFrame:
        """Округляет числовые колонки до 2 знаков"""
        numeric_cols = result.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if col != 'nm_id':
                result[col] = result[col].round(2)
        return result

    def _create_summary_row(self, df: pd.DataFrame) -> pd.DataFrame:
        """Создает строку с итоговыми значениями (первая строка в Excel - ОБЩАЯ)"""
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        summary_data = {'wb_article': 'ИТОГО'}
        
        for col in numeric_cols:
            # Логика расчета итогов для процентов (пересчет из агрегированных сумм)
            if col == 'margin':
                total_revenue = df['sales_with_spp'].sum()
                total_expenses = df['total_expenses'].sum()
                summary_data[col] = ((total_revenue - total_expenses) / total_revenue * 100) if total_revenue else 0.0
            elif col == 'profitability':
                total_profit = df['profit'].sum()
                total_exp = df['total_expenses'].sum()
                summary_data[col] = (total_profit / total_exp * 100) if total_exp else 0.0
            elif col == 'buyout_percent':
                total_sales_qty = df['sales_qty'].sum()
                total_deliveries_qty = df['deliveries_qty'].sum()
                summary_data[col] = (total_sales_qty / total_deliveries_qty * 100) if total_deliveries_qty else 0.0
            elif col == 'drr':
                total_ad = df['ad_expenses'].sum()
                total_rev = df['sales_with_spp'].sum()
                summary_data[col] = (total_ad / total_rev * 100) if total_rev else 0.0
            elif col in ['avg_sale_price', 'profit_per_unit', 'logistics_per_sale', 'logistics_per_unit']:
                # Средние величины пересчитываем как Сумма / Сумма Qty
                qty_denominator = 0.0
                numerator = 0.0
                if col == 'avg_sale_price':
                    qty_denominator = df['sales_qty'].sum()
                    numerator = df['sales_with_spp'].sum()
                elif col == 'profit_per_unit':
                    qty_denominator = df['sales_qty'].sum()
                    numerator = df['profit'].sum()
                elif col == 'logistics_per_sale':
                    qty_denominator = df['sales_qty'].sum()
                    numerator = df['logistics_total'].sum()
                elif col == 'logistics_per_unit':
                    qty_denominator = df['deliveries_qty'].sum()
                    numerator = df['logistics_total'].sum()
                
                summary_data[col] = (numerator / qty_denominator) if qty_denominator else 0.0
            else:
                # Суммируем деньги и количества, явно приводя к float
                summary_data[col] = float(df[col].sum())
        
        # Заполняем пустые строковые колонки пустой строкой вместо None для корректного типа
        for col in df.select_dtypes(include=['object', 'string']).columns:
            if col not in summary_data:
                summary_data[col] = ""
                
        return pd.DataFrame([summary_data])
