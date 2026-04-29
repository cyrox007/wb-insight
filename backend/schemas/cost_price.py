from pydantic import BaseModel, Field, field_validator


class UnitEconomyMetrics(BaseModel):
    """Модель метрик unit-экономики"""

    revenue: float = Field(..., description="Выручка (retail_amount)")
    total_cost: float = Field(..., description="Общая себестоимость (cost_price × quantity)")
    payout: float = Field(..., description="К выплате (ppvz_for_pay)")
    commission: float = Field(..., description="Комиссия маркетплейса")
    logistics: float = Field(..., description="Логистика (доставка + возвраты)")
    penalty: float = Field(..., description="Штрафы")
    storage: float = Field(..., description="Хранение")

    # Расчётные метрики
    profit: float = Field(..., description="Прибыль = payout - total_cost")
    margin_percent: float = Field(..., description="Маржинальность % = (profit / revenue) × 100")
    drr_percent: float = Field(..., description="Доля расходов % = ((commission + logistics + penalty) / revenue) × 100")
    profitability_percent: float = Field(..., description="Рентабельность % = (profit / payout) × 100")