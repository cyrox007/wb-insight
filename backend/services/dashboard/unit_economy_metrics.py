"""Corrected Unit Economy aggregation layer."""

import numpy as np
import pandas as pd

from services.dashboard.unit_economy_service import (
    UnitEconomyMetricsService as _LegacyUnitEconomyMetricsService,
)


class UnitEconomyMetricsService(_LegacyUnitEconomyMetricsService):
    def __init__(self, tax_rate: float = 0.2):
        super().__init__(tax_rate=tax_rate)
        self._manual_expenses_map: dict[int, float] = {}
        self._manual_expenses_total = 0.0

    def calculate_all_metrics(
        self,
        df: pd.DataFrame,
        advertising_costs_map: dict[int, float] | None = None,
        manual_expenses_map: dict[int, float] | None = None,
        manual_expenses_total: float = 0.0,
    ) -> pd.DataFrame:
        self._manual_expenses_map = manual_expenses_map or {}
        self._manual_expenses_total = float(manual_expenses_total or 0)
        return super().calculate_all_metrics(
            df,
            advertising_costs_map=advertising_costs_map,
        )

    def _calculate_tax_and_advertising_metrics(
        self,
        result: pd.DataFrame,
        advertising_costs_map: dict[int, float] | None = None,
    ) -> None:
        super()._calculate_tax_and_advertising_metrics(
            result,
            advertising_costs_map=advertising_costs_map,
        )
        if self._manual_expenses_map:
            result["other_expenses"] = result["nm_id"].map(
                self._manual_expenses_map
            ).fillna(0)
        else:
            result["other_expenses"] = 0.0

    def _calculate_profitability_metrics(self, result: pd.DataFrame) -> None:
        result["total_costs"] = (
            result["product_cost"]
            + result["delivery_rub"]
            + result["storage_fee"]
            + result["acquiring_fee"]
            + result["penalty"]
            + result["deduction"]
            + result["acceptance"]
            + result["tax"]
            + result["advertising_cost"]
            + result["other_expenses"]
            + result["ppvz_sales_commission"]
            + result["ppvz_vw_nds"]
        )
        result["profit"] = result["sales_without_spp"] - result["total_costs"]
        result["profit_per_unit"] = np.where(
            result["sales_quantity"] > 0,
            result["profit"] / result["sales_quantity"],
            0,
        )
        result["margin"] = np.where(
            result["sales_without_spp"] > 0,
            result["profit"] / result["sales_without_spp"] * 100,
            0,
        )
        result["roi"] = np.where(
            result["total_costs"] > 0,
            result["profit"] / result["total_costs"] * 100,
            0,
        )
        result["avg_selling_price"] = np.where(
            result["sales_quantity"] > 0,
            result["sales_without_spp"] / result["sales_quantity"],
            0,
        )

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
            "other_expenses",
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

        mapped_expenses = self._sum(df, "other_expenses")
        missing_expenses = max(0.0, self._manual_expenses_total - mapped_expenses)
        if "other_expenses" in summary:
            summary["other_expenses"] = mapped_expenses + missing_expenses
        if "total_costs" in summary:
            summary["total_costs"] = self._sum(df, "total_costs") + missing_expenses
        if "profit" in summary:
            summary["profit"] = self._sum(df, "profit") - missing_expenses

        sales_qty = self._sum(df, "sales_quantity")
        delivery_qty = self._sum(df, "delivery_quantity")
        net_qty = self._sum(df, "net_quantity")
        sales_without_spp = self._sum(df, "sales_without_spp")
        sales_with_spp = self._sum(df, "sales_with_spp")
        commission = self._sum(df, "ppvz_sales_commission")
        logistics = self._sum(df, "delivery_rub")
        advertising = self._sum(df, "advertising_cost")
        product_cost = self._sum(df, "product_cost")
        total_costs = float(summary.get("total_costs", 0) or 0)
        profit = float(summary.get("profit", 0) or 0)

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
