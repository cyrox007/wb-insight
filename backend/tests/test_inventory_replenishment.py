from datetime import date

import pytest

from services.dashboard.inventory_replenishment import (
    _completed_period_bounds,
    calculate_inventory_recommendation,
)


def test_critical_stock_uses_fbo_only_and_targets_thirty_days():
    item = calculate_inventory_recommendation(
        nm_id=101,
        product_name="Товар",
        stock_units=30,
        in_way_to_client=100,
        in_way_from_client=50,
        orders_count=90,
    )

    assert item.orders_per_day == 3
    assert item.coverage_days == 10
    assert item.status == "critical"
    assert item.recommended_supply_units == 60
    assert item.in_way_to_client == 100
    assert item.in_way_from_client == 50


def test_replenish_status_between_fourteen_and_thirty_days():
    item = calculate_inventory_recommendation(
        nm_id=102,
        stock_units=60,
        orders_count=90,
    )

    assert item.coverage_days == 20
    assert item.status == "replenish"
    assert item.recommended_supply_units == 30


def test_healthy_stock_never_returns_negative_supply():
    item = calculate_inventory_recommendation(
        nm_id=103,
        stock_units=120,
        orders_count=90,
    )

    assert item.coverage_days == 40
    assert item.status == "healthy"
    assert item.recommended_supply_units == 0
    assert item.excess_units == 30


def test_no_demand_stock_is_separated_from_replenishment():
    item = calculate_inventory_recommendation(
        nm_id=104,
        stock_units=50,
        orders_count=0,
    )

    assert item.orders_per_day == 0
    assert item.coverage_days is None
    assert item.status == "no_demand"
    assert item.recommended_supply_units == 0
    assert item.excess_units == 50


def test_out_of_stock_with_demand_is_highest_risk():
    item = calculate_inventory_recommendation(
        nm_id=105,
        stock_units=0,
        orders_count=30,
    )

    assert item.orders_per_day == 1
    assert item.coverage_days == 0
    assert item.status == "out_of_stock"
    assert item.recommended_supply_units == 30


def test_completed_period_excludes_current_partial_day():
    start_date, end_date, start_dt, end_exclusive_dt = _completed_period_bounds(
        date(2026, 9, 15)
    )

    assert start_date == date(2026, 8, 16)
    assert end_date == date(2026, 9, 14)
    assert (end_exclusive_dt - start_dt).total_seconds() == pytest.approx(30 * 86400)


def test_replenishment_parameters_are_validated():
    with pytest.raises(ValueError):
        calculate_inventory_recommendation(
            nm_id=106,
            stock_units=1,
            orders_count=1,
            lookback_days=0,
        )

    with pytest.raises(ValueError):
        calculate_inventory_recommendation(
            nm_id=106,
            stock_units=1,
            orders_count=1,
            critical_days=31,
            target_days=30,
        )
