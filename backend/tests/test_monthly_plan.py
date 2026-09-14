from datetime import date

import pytest

from handlers.dashboard.main_handler import _parse_plan_month, _parse_revenue_target
from services.dashboard.monthly_plan_service import calculate_monthly_plan_metrics


def test_monthly_plan_uses_actual_calendar_length_and_order_run_rate():
    metrics = calculate_monthly_plan_metrics(
        fact_revenue=140_000,
        revenue_target=300_000,
        ordered_amount=120_000,
        ordered_count=120,
        today=date(2026, 9, 14),
    )

    assert metrics.days_in_month == 30
    assert metrics.elapsed_days == 14
    assert metrics.remaining_days == 16
    assert metrics.done_percent == pytest.approx(46.67, abs=0.01)
    assert metrics.forecast_revenue == 300_000
    assert metrics.required_revenue_per_day == 10_000
    assert metrics.required_orders_per_day == 10


def test_monthly_plan_handles_leap_february():
    metrics = calculate_monthly_plan_metrics(
        fact_revenue=145_000,
        revenue_target=290_000,
        ordered_amount=145_000,
        ordered_count=145,
        today=date(2028, 2, 14),
    )

    assert metrics.days_in_month == 29
    assert metrics.remaining_days == 15
    assert metrics.forecast_revenue == pytest.approx(300_357.14, abs=0.01)
    assert metrics.required_revenue_per_day == pytest.approx(9_666.67, abs=0.01)
    assert metrics.required_orders_per_day == pytest.approx(9.67, abs=0.01)


def test_missing_plan_returns_null_plan_metrics_instead_of_fabricated_target():
    metrics = calculate_monthly_plan_metrics(
        fact_revenue=0,
        revenue_target=None,
        ordered_amount=0,
        ordered_count=0,
        today=date(2026, 9, 14),
    )

    assert metrics.revenue_target is None
    assert metrics.done_percent is None
    assert metrics.required_revenue_per_day is None
    assert metrics.required_orders_per_day is None
    assert metrics.forecast_revenue == 0


def test_plan_target_already_reached_requires_zero_daily_run_rate():
    metrics = calculate_monthly_plan_metrics(
        fact_revenue=310_000,
        revenue_target=300_000,
        ordered_amount=250_000,
        ordered_count=100,
        today=date(2026, 9, 14),
    )

    assert metrics.done_percent == pytest.approx(103.33, abs=0.01)
    assert metrics.required_revenue_per_day == 0
    assert metrics.required_orders_per_day == 0


def test_plan_input_is_normalized_and_validated():
    assert _parse_plan_month("2026-09-17") == date(2026, 9, 1)
    assert _parse_revenue_target("123456.789") == pytest.approx(123456.79)

    with pytest.raises(ValueError):
        _parse_revenue_target(0)
    with pytest.raises(ValueError):
        _parse_revenue_target(-1)
    with pytest.raises(ValueError):
        _parse_revenue_target("not-a-number")
