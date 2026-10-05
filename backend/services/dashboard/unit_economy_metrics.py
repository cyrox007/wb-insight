"""Канонический расчёт финансовых показателей юнит-экономики."""

import numpy as np
import pandas as pd


class UnitEconomyMetricsService:
    """Считает P&L по единой политике операций Wildberries."""

    _NUMERIC_COLUMNS = (
        "quantity",
        "retail_price_with_disc_rub",
        "retail_amount",
        "delivery_amount",
        "return_amount",
        "ppvz_kvw_prc_base",
        "ppvz_sales_commission",
        "ppvz_for_pay",
        "delivery_rub",
        "return_rub",
        "rebill_logistic_cost",
        "acquiring_fee",
        "storage_fee",
        "penalty",
        "deduction",
        "acceptance",
        "additional_payment",
        "product_cost",
        "ppvz_vw_nds",
    )
    _CORRECTION_OPERATIONS = {
        "Корректировка эквайринга",
        "Коррекция продаж",
        "Коррекция возвратов",
        "Компенсация ущерба",
    }
    _FINAL_COLUMNS = (
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
        "financial_adjustments",
        "additional_payment",
        "correction_acquiring",
        "correction_sales_sale",
        "correction_sales_return",
        "correction_returns",
        "compensation",
        "unallocated_wb_expenses",
        "unallocated_financial_adjustments",
    )

    def __init__(self, tax_rate: float = 0.2):
        self.tax_rate = float(tax_rate or 0)

    def calculate_all_metrics(
        self,
        df: pd.DataFrame,
        advertising_costs_map: dict[int, float] | None = None,
        manual_expenses_map: dict[int, float] | None = None,
        manual_expenses_total: float = 0.0,
    ) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()

        frame = self._prepare_frame(df)
        advertising = advertising_costs_map or {}
        manual = manual_expenses_map or {}

        product_ids = sorted(
            int(value)
            for value in frame["nm_id"].dropna().unique()
            if int(value) > 0
        )
        product_rows = [
            self._calculate_scope(
                frame.loc[frame["nm_id"] == nm_id],
                nm_id=nm_id,
                advertising_cost=float(advertising.get(nm_id, 0) or 0),
                manual_expenses=float(manual.get(nm_id, 0) or 0),
            )
            for nm_id in product_ids
        ]

        summary = self._calculate_scope(
            frame,
            nm_id=None,
            advertising_cost=sum(float(value or 0) for value in advertising.values()),
            manual_expenses=float(manual_expenses_total or 0),
        )
        unallocated = frame.loc[frame["nm_id"].fillna(0) <= 0]
        summary["unallocated_wb_expenses"] = self._marketplace_expenses(unallocated)
        summary["unallocated_financial_adjustments"] = self._financial_adjustments(
            unallocated
        )

        rows = [summary, *product_rows]
        result = pd.DataFrame(rows)
        for column in self._FINAL_COLUMNS:
            if column not in result.columns:
                result[column] = 0.0
        result = result[list(self._FINAL_COLUMNS)]
        return self._round_numeric_columns(result)

    def _prepare_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        frame = df.copy()
        required_text = ("nm_id", "supplier_oper_name", "doc_type_name")
        missing = [column for column in required_text if column not in frame.columns]
        if missing:
            raise ValueError(f"Отсутствуют необходимые колонки: {missing}")

        for column in self._NUMERIC_COLUMNS:
            if column not in frame.columns:
                frame[column] = 0.0
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
        frame["nm_id"] = pd.to_numeric(frame["nm_id"], errors="coerce").fillna(0).astype(int)
        frame["supplier_oper_name"] = frame["supplier_oper_name"].fillna("").astype(str)
        frame["doc_type_name"] = frame["doc_type_name"].fillna("").astype(str)
        return frame

    @staticmethod
    def _operation_masks(frame: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
        operation = frame["supplier_oper_name"]
        document = frame["doc_type_name"]
        sales = (operation == "Продажа") | (
            (operation == "Коррекция продаж") & (document == "Продажа")
        )
        returns = (
            (operation == "Возврат")
            | ((operation == "Коррекция продаж") & (document == "Возврат"))
            | (operation == "Коррекция возвратов")
        )
        return sales, returns

    @staticmethod
    def _absolute_sum(frame: pd.DataFrame, column: str) -> float:
        if frame.empty:
            return 0.0
        return float(frame[column].abs().sum())

    @staticmethod
    def _sum(frame: pd.DataFrame, column: str) -> float:
        if frame.empty:
            return 0.0
        return float(frame[column].sum())

    @staticmethod
    def _ratio(numerator: float, denominator: float, multiplier: float = 1.0) -> float:
        if denominator <= 0:
            return 0.0
        return numerator / denominator * multiplier

    def _marketplace_expenses(self, frame: pd.DataFrame) -> float:
        if frame.empty:
            return 0.0
        return float(
            frame["ppvz_sales_commission"].sum()
            + frame["delivery_rub"].sum()
            + frame["return_rub"].sum()
            + frame["rebill_logistic_cost"].sum()
            + frame["acquiring_fee"].sum()
            + frame["storage_fee"].sum()
            + frame["penalty"].sum()
            + frame["deduction"].sum()
            + frame["acceptance"].sum()
            + frame["ppvz_vw_nds"].sum()
        )

    def _financial_adjustments(self, frame: pd.DataFrame) -> float:
        if frame.empty:
            return 0.0

        additional = frame["additional_payment"].sum()
        correction_mask = frame["supplier_oper_name"].isin(self._CORRECTION_OPERATIONS)
        correction_rows = frame.loc[correction_mask]
        if correction_rows.empty:
            return float(additional)

        no_explicit_additional = correction_rows["additional_payment"].abs() < 0.000001
        no_revenue_amount = correction_rows["retail_amount"].abs() < 0.000001
        fallback = correction_rows.loc[
            no_explicit_additional & no_revenue_amount,
            "ppvz_for_pay",
        ].sum()
        return float(additional + fallback)

    def _signed_payout(self, frame: pd.DataFrame) -> float:
        sales, returns = self._operation_masks(frame)
        commercial = sales | returns
        sale_payout = self._absolute_sum(frame.loc[sales], "ppvz_for_pay")
        return_payout = self._absolute_sum(frame.loc[returns], "ppvz_for_pay")
        other_payout = self._sum(frame.loc[~commercial], "ppvz_for_pay")
        return sale_payout - return_payout + other_payout

    def _correction_value(
        self,
        frame: pd.DataFrame,
        operation: str,
        document: str | None = None,
    ) -> float:
        mask = frame["supplier_oper_name"] == operation
        if document is not None:
            mask &= frame["doc_type_name"] == document
        return self._sum(frame.loc[mask], "ppvz_for_pay")

    def _calculate_scope(
        self,
        frame: pd.DataFrame,
        *,
        nm_id: int | None,
        advertising_cost: float,
        manual_expenses: float,
    ) -> dict[str, float | int | None]:
        sales, returns = self._operation_masks(frame)
        sales_frame = frame.loc[sales]
        returns_frame = frame.loc[returns]

        sales_without_spp = (
            self._absolute_sum(sales_frame, "retail_price_with_disc_rub")
            - self._absolute_sum(returns_frame, "retail_price_with_disc_rub")
        )
        sales_with_spp = (
            self._absolute_sum(sales_frame, "retail_amount")
            - self._absolute_sum(returns_frame, "retail_amount")
        )
        returns_amount = self._absolute_sum(returns_frame, "retail_amount")
        sales_quantity = self._absolute_sum(sales_frame, "quantity")
        returns_quantity = self._absolute_sum(returns_frame, "quantity")
        net_quantity = sales_quantity - returns_quantity
        delivery_quantity = self._absolute_sum(sales_frame, "delivery_amount")

        sale_cost = self._absolute_sum(
            sales_frame.assign(
                _cost=sales_frame["product_cost"].abs() * sales_frame["quantity"].abs()
            ),
            "_cost",
        )
        return_cost = self._absolute_sum(
            returns_frame.assign(
                _cost=returns_frame["product_cost"].abs()
                * returns_frame["quantity"].abs()
            ),
            "_cost",
        )
        product_cost = sale_cost - return_cost

        commission = self._sum(frame, "ppvz_sales_commission")
        acquiring = self._sum(frame, "acquiring_fee")
        logistics = (
            self._sum(frame, "delivery_rub")
            + self._sum(frame, "return_rub")
            + self._sum(frame, "rebill_logistic_cost")
        )
        storage = self._sum(frame, "storage_fee")
        penalty = self._sum(frame, "penalty")
        deduction = self._sum(frame, "deduction")
        acceptance = self._sum(frame, "acceptance")
        reward_vat = self._sum(frame, "ppvz_vw_nds")
        tax = sales_with_spp * self.tax_rate
        adjustments = self._financial_adjustments(frame)

        marketplace_costs = (
            commission
            + logistics
            + acquiring
            + storage
            + penalty
            + deduction
            + acceptance
            + reward_vat
        )
        total_costs = (
            product_cost
            + marketplace_costs
            + tax
            + advertising_cost
            + manual_expenses
        )
        profit = sales_without_spp + adjustments - total_costs

        row: dict[str, float | int | None] = {
            "nm_id": nm_id,
            "sales_without_spp": sales_without_spp,
            "sales_with_spp": sales_with_spp,
            "returns_amount": returns_amount,
            "sales_quantity": sales_quantity,
            "delivery_quantity": delivery_quantity,
            "returns_quantity": returns_quantity,
            "buyout_percent": self._ratio(sales_quantity, delivery_quantity, 100),
            "net_quantity": net_quantity,
            "ppvz_kvw_prc_base": self._ratio(commission, sales_without_spp, 100),
            "ppvz_sales_commission": commission,
            "acquiring_fee": acquiring,
            "ppvz_for_pay": self._signed_payout(frame),
            "delivery_rub": logistics,
            "logistics_per_delivery": self._ratio(logistics, delivery_quantity),
            "logistics_per_sale": self._ratio(logistics, sales_quantity),
            "storage_fee": storage,
            "penalty": penalty,
            "deduction": deduction,
            "acceptance": acceptance,
            "tax": tax,
            "advertising_cost": advertising_cost,
            "other_expenses": manual_expenses,
            "drr": self._ratio(advertising_cost, sales_with_spp, 100),
            "product_cost": product_cost,
            "avg_product_cost": self._ratio(product_cost, net_quantity),
            "total_costs": total_costs,
            "profit": profit,
            "profit_per_unit": self._ratio(profit, sales_quantity),
            "margin": self._ratio(profit, sales_without_spp, 100),
            "roi": self._ratio(profit, total_costs, 100),
            "avg_selling_price": self._ratio(sales_without_spp, sales_quantity),
            "financial_adjustments": adjustments,
            "additional_payment": self._sum(frame, "additional_payment"),
            "correction_acquiring": self._correction_value(
                frame, "Корректировка эквайринга"
            ),
            "correction_sales_sale": self._correction_value(
                frame, "Коррекция продаж", "Продажа"
            ),
            "correction_sales_return": self._correction_value(
                frame, "Коррекция продаж", "Возврат"
            ),
            "correction_returns": self._correction_value(
                frame, "Коррекция возвратов"
            ),
            "compensation": self._correction_value(frame, "Компенсация ущерба"),
            "unallocated_wb_expenses": 0.0,
            "unallocated_financial_adjustments": 0.0,
        }
        return row

    @staticmethod
    def _round_numeric_columns(result: pd.DataFrame) -> pd.DataFrame:
        numeric_columns = result.select_dtypes(include=[np.number]).columns
        for column in numeric_columns:
            if column != "nm_id":
                result[column] = result[column].round(2)
        return result
