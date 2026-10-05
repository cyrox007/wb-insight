import pandas as pd
import pytest

from handlers.dashboard.unit_economy_handler import _format_response
from services.dashboard.financial_semantics import FinancialMetricsResult
from services.dashboard.unit_economy_metrics import UnitEconomyMetricsService


def _sample_report_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "nm_id": 101,
                "supplier_oper_name": "Продажа",
                "doc_type_name": "Продажа",
                "quantity": 2,
                "retail_price_with_disc_rub": 1000.0,
                "retail_amount": 900.0,
                "delivery_amount": 2,
                "ppvz_kvw_prc_base": 10.0,
                "ppvz_sales_commission": 100.0,
                "ppvz_for_pay": 800.0,
                "delivery_rub": 50.0,
                "acquiring_fee": 10.0,
                "storage_fee": 5.0,
                "penalty": 0.0,
                "deduction": 0.0,
                "acceptance": 0.0,
                "product_cost": 200.0,
                "ppvz_vw_nds": 0.0,
            },
            {
                "nm_id": 202,
                "supplier_oper_name": "Продажа",
                "doc_type_name": "Продажа",
                "quantity": 1,
                "retail_price_with_disc_rub": 500.0,
                "retail_amount": 450.0,
                "delivery_amount": 1,
                "ppvz_kvw_prc_base": 10.0,
                "ppvz_sales_commission": 50.0,
                "ppvz_for_pay": 400.0,
                "delivery_rub": 25.0,
                "acquiring_fee": 5.0,
                "storage_fee": 2.0,
                "penalty": 0.0,
                "deduction": 0.0,
                "acceptance": 0.0,
                "product_cost": 100.0,
                "ppvz_vw_nds": 0.0,
            },
        ]
    )


def _audit_control_sale() -> dict:
    return {
        "nm_id": 101,
        "supplier_oper_name": "Продажа",
        "doc_type_name": "Продажа",
        "quantity": 1,
        "retail_price_with_disc_rub": 1000.0,
        "retail_amount": 900.0,
        "delivery_amount": 1,
        "ppvz_sales_commission": 100.0,
        "ppvz_for_pay": 800.0,
        "delivery_rub": 50.0,
        "acquiring_fee": 10.0,
        "storage_fee": 5.0,
        "product_cost": 100.0,
    }


def test_unit_economy_summary_uses_current_columns_and_weighted_ratios():
    service = UnitEconomyMetricsService(tax_rate=0.10)

    result = service.calculate_all_metrics(
        _sample_report_rows(),
        advertising_costs_map={101: 100.0, 202: 50.0},
    )

    assert len(result) == 3
    summary = result.iloc[0]

    assert summary["sales_without_spp"] == pytest.approx(1500.0)
    assert summary["sales_with_spp"] == pytest.approx(1350.0)
    assert summary["ppvz_sales_commission"] == pytest.approx(150.0)
    assert summary["advertising_cost"] == pytest.approx(150.0)
    assert summary["tax"] == pytest.approx(135.0)
    assert summary["product_cost"] == pytest.approx(500.0)
    assert summary["total_costs"] == pytest.approx(1032.0)
    assert summary["profit"] == pytest.approx(468.0)

    assert summary["buyout_percent"] == pytest.approx(100.0)
    assert summary["ppvz_kvw_prc_base"] == pytest.approx(10.0)
    assert summary["drr"] == pytest.approx(11.11, abs=0.01)
    assert summary["margin"] == pytest.approx(31.2, abs=0.01)
    assert summary["roi"] == pytest.approx(45.35, abs=0.01)
    assert summary["avg_selling_price"] == pytest.approx(500.0)
    assert summary["profit_per_unit"] == pytest.approx(156.0)


def test_audit_control_example_has_one_canonical_profit_and_drr():
    service = UnitEconomyMetricsService(tax_rate=0.10)
    result = service.calculate_all_metrics(
        pd.DataFrame([_audit_control_sale()]),
        advertising_costs_map={101: 100.0},
    )

    summary = result.iloc[0]
    assert summary["profit"] == pytest.approx(545.0)
    assert summary["drr"] == pytest.approx(11.11, abs=0.01)
    assert summary["total_costs"] == pytest.approx(455.0)


def test_standalone_logistics_operation_reduces_total_profit():
    service = UnitEconomyMetricsService(tax_rate=0.10)
    sale = _audit_control_sale()
    standalone_logistics = {
        "nm_id": 0,
        "supplier_oper_name": "Логистика",
        "doc_type_name": "",
        "quantity": 0,
        "delivery_rub": 300.0,
    }

    baseline = service.calculate_all_metrics(
        pd.DataFrame([sale]),
        advertising_costs_map={101: 100.0},
    )
    with_logistics = service.calculate_all_metrics(
        pd.DataFrame([sale, standalone_logistics]),
        advertising_costs_map={101: 100.0},
    )

    baseline_summary = baseline.iloc[0]
    changed_summary = with_logistics.iloc[0]
    product = with_logistics[with_logistics["nm_id"] == 101].iloc[0]

    assert changed_summary["delivery_rub"] == pytest.approx(
        baseline_summary["delivery_rub"] + 300.0
    )
    assert changed_summary["profit"] == pytest.approx(
        baseline_summary["profit"] - 300.0
    )
    assert changed_summary["unallocated_wb_expenses"] == pytest.approx(300.0)
    assert product["profit"] == pytest.approx(545.0)


def test_returns_reduce_revenue_payout_quantity_and_cost_of_goods():
    service = UnitEconomyMetricsService(tax_rate=0.0)
    sale = {
        "nm_id": 101,
        "supplier_oper_name": "Продажа",
        "doc_type_name": "Продажа",
        "quantity": 1,
        "retail_price_with_disc_rub": 1000.0,
        "retail_amount": 900.0,
        "ppvz_for_pay": 800.0,
        "product_cost": 100.0,
    }
    returned = {
        **sale,
        "supplier_oper_name": "Возврат",
        "doc_type_name": "Возврат",
    }

    result = service.calculate_all_metrics(pd.DataFrame([sale, returned]))
    summary = result.iloc[0]

    assert summary["sales_without_spp"] == pytest.approx(0.0)
    assert summary["sales_with_spp"] == pytest.approx(0.0)
    assert summary["ppvz_for_pay"] == pytest.approx(0.0)
    assert summary["net_quantity"] == pytest.approx(0.0)
    assert summary["product_cost"] == pytest.approx(0.0)
    assert summary["profit"] == pytest.approx(0.0)


def test_unit_economy_response_maps_internal_metrics_to_frontend_contract():
    service = UnitEconomyMetricsService(tax_rate=0.10)
    result = service.calculate_all_metrics(
        _sample_report_rows(),
        advertising_costs_map={101: 100.0, 202: 50.0},
    )
    financial = FinancialMetricsResult(
        metrics=result,
        profit_complete=False,
        cost_coverage_percent=80.0,
        cost_missing_operations=2,
        products_with_cost=1,
        products_without_cost=1,
    )

    response = _format_response(result, financial=financial)

    assert response["status"] == "success"
    summary = response["data"]["summary"]
    table = response["data"]["table"]

    assert summary["wb_commission_percent"] == pytest.approx(10.0)
    assert summary["wb_commission_amount"] == pytest.approx(150.0)
    assert summary["to_pay_seller"] == pytest.approx(1200.0)
    assert summary["logistics"] == pytest.approx(75.0)
    assert summary["drr"] == pytest.approx(11.11, abs=0.01)
    assert summary["cost_price"] == pytest.approx(500.0)
    assert summary["marginality"] == pytest.approx(31.2, abs=0.01)
    assert summary["profitability"] == pytest.approx(45.35, abs=0.01)
    assert summary["profit"] == pytest.approx(468.0)
    assert summary["profit_complete"] is False
    assert summary["cost_coverage_percent"] == pytest.approx(80.0)
    assert summary["cost_missing_operations"] == 2
    assert "Прибыль неполная" in summary["profit_warning"]

    assert len(table) == 2
    first = next(row for row in table if row["wb_article"] == 101)
    assert first["sales_qty"] == 2
    assert first["deliveries_qty"] == 2
    assert first["acquiring"] == pytest.approx(10.0)
    assert first["ad_expenses"] == pytest.approx(100.0)
    assert first["cost_price_total"] == pytest.approx(400.0)
    assert first["total_expenses"] == pytest.approx(755.0)
    assert first["avg_sale_price"] == pytest.approx(500.0)


def test_manual_expenses_match_period_semantics_without_fake_allocation():
    service = UnitEconomyMetricsService(tax_rate=0.10)
    result = service.calculate_all_metrics(
        _sample_report_rows(),
        advertising_costs_map={101: 100.0, 202: 50.0},
        manual_expenses_map={101: 30.0},
        manual_expenses_total=80.0,
    )

    summary = result.iloc[0]
    first = result[result["nm_id"] == 101].iloc[0]
    second = result[result["nm_id"] == 202].iloc[0]

    # 30 ₽ явно относятся к SKU 101. Остальные 50 ₽ уменьшают только общий P&L:
    # система не придумывает распределение расхода по товарам.
    assert first["other_expenses"] == pytest.approx(30.0)
    assert second["other_expenses"] == pytest.approx(0.0)
    assert first["total_costs"] == pytest.approx(785.0)
    assert summary["other_expenses"] == pytest.approx(80.0)
    assert summary["total_costs"] == pytest.approx(1112.0)
    assert summary["profit"] == pytest.approx(388.0)
    assert summary["margin"] == pytest.approx(25.87, abs=0.01)
    assert summary["roi"] == pytest.approx(34.89, abs=0.01)

    response = _format_response(result)
    assert response["data"]["summary"]["other_expenses"] == pytest.approx(80.0)
    row_101 = next(
        row for row in response["data"]["table"] if row["wb_article"] == 101
    )
    assert row_101["other_expenses"] == pytest.approx(30.0)
