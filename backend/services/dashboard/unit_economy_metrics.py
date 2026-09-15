"""Corrected Unit Economy aggregation layer.

The legacy service still contains obsolete summary-column names from an older
API shape. This subclass keeps the proven per-SKU calculations but defines the
current output columns and computes aggregate ratios from their real
numerators/denominators instead of summing percentages.
"""

import numpy as np
import pandas as pd

from services.dashboard.unit_economy_service import (
    UnitEconomyMetricsService as _LegacyUnitEconomyMetricsService,
)


class UnitEconomyMetricsService(_LegacyUnitEconomyMetricsService):
    def _select_final_columns(self, result: pd.DataFrame) -> pd.DataFrame:
        final_columns = [
            "nm_id",
            "sales_without_spp",
            "sales_with_spp",
            "returns_amount",
            "sales_quantity",
            "delivery_quantity",
            "returns_quantity",
            "buyout_percent",
            "net_quantity",
            "ppvz_kvw_prc_base",
            "ppvz_sales_commission",
            "acquiring_fee",
            "ppvz_for_pay",
            "delivery_rub",
            "logistics_per_delivery",
            "logistics_per_sale",
            "storage_fee",
            "penalty",
            "deduction",
            "acceptance",
            "tax",
            "advertising_cost",
            "drr",
            "product_cost",
            "avg_product_cost",
            "total_costs",
            "profit",
            "profit_per_unit",
            "margin",
            "roi",
            "avg_selling_price",
            "correction_acquiring",
            "correction_sales_sale",
            "correction_sales_return",
            "correction_returns",
            "compensation",
        ]
        return result[[column for column in final_columns if column in result.columns]]

    @staticmethod
    def _sum(df: pd.DataFrame, column: str) -> float:
        if column not in df.columns:
            return 0.0
        return float(df[column].fillna(0).sum())

    @staticmethod
    def _ratio(numerator: float, denominator: float, multiplier: float = 1.0) -> float:
        if not denominator:
            return 0.0
        return numerator / denominator * multiplier

    def _create_summary_row(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=df.columns)

        ratio_columns = {
            "buyout_percent",
            "ppvz_kvw_prc_base",
            "logistics_per_delivery",
            "logistics_per_sale",
            "drr",
            "avg_product_cost",
            "profit_per_unit",
            "margin",
            "roi",
            "avg_selling_price",
        }

        summary: dict[str, float | int | None] = {}
        for column in df.columns:
            if column == "nm_id":
                summary[column] = None
            elif column not in ratio_columns:
                summary[column] = self._sum(df, column)

        sales_qty = self._sum(df, "sales_quantity")
        delivery_qty = self._sum(df, "delivery_quantity")
        net_qty = self._sum(df, "net_quantity")
        sales_without_spp = self._sum(df, "sales_without_spp")
        sales_with_spp = self._sum(df, "sales_with_spp")
        commission = self._sum(df, "ppvz_sales_commission")
        logistics = self._sum(df, "delivery_rub")
        advertising = self._sum(df, "advertising_cost")
        product_cost = self._sum(df, "product_cost")
        total_costs = self._sum(df, "total_costs")
        profit = self._sum(df, "profit")

        summary["buyout_percent"] = self._ratio(sales_qty, delivery_qty, 100)
        summary["ppvz_kvw_prc_base"] = self._ratio(
            commission, sales_without_spp, 100
        )
        summary["logistics_per_delivery"] = self._ratio(logistics, delivery_qty)
        summary["logistics_per_sale"] = self._ratio(logistics, sales_qty)
        summary["drr"] = self._ratio(advertising, sales_with_spp, 100)
        summary["avg_product_cost"] = self._ratio(product_cost, net_qty)
        summary["profit_per_unit"] = self._ratio(profit, sales_qty)
        summary["margin"] = self._ratio(profit, sales_without_spp, 100)
        summary["roi"] = self._ratio(profit, total_costs, 100)
        summary["avg_selling_price"] = self._ratio(sales_without_spp, sales_qty)

        for key, value in list(summary.items()):
            if isinstance(value, (int, float, np.number)):
                summary[key] = round(float(value), 2)

        return pd.DataFrame([summary], columns=df.columns)
