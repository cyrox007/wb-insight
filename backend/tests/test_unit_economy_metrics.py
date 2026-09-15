import pandas as pd
import pytest

from handlers.dashboard.unit_economy_handler import _format_response
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

    # Percentages/averages must be recomputed from aggregate numerators and
    # denominators, not summed across SKU rows.
    assert summary["buyout_percent"] == pytest.approx(100.0)
    assert summary["ppvz_kvw_prc_base"] == pytest.approx(10.0)
    assert summary["drr"] == pytest.approx(11.11, abs=0.01)
    assert summary["margin"] == pytest.approx(31.2, abs=0.01)
    assert summary["roi"] == pytest.approx(45.35, abs=0.01)
    assert summary["avg_selling_price"] == pytest.approx(500.0)
    assert summary["profit_per_unit"] == pytest.approx(156.0)


def test_unit_economy_response_maps_internal_metrics_to_frontend_contract():
    service = UnitEconomyMetricsService(tax_rate=0.10)
    result = service.calculate_all_metrics(
        _sample_report_rows(),
        advertising_costs_map={101: 100.0, 202: 50.0},
    )

    response = _format_response(result)

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

    assert len(table) == 2
    first = next(row for row in table if row["wb_article"] == 101)
    assert first["sales_qty"] == 2
    assert first["deliveries_qty"] == 2
    assert first["acquiring"] == pytest.approx(10.0)
    assert first["ad_expenses"] == pytest.approx(100.0)
    assert first["cost_price_total"] == pytest.approx(400.0)
    assert first["total_expenses"] == pytest.approx(755.0)
    assert first["avg_sale_price"] == pytest.approx(500.0)
