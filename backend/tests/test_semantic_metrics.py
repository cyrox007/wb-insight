from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from handlers.dashboard import ads_handler, main_handler
from services.dashboard.semantic_metrics import (
    AdvertisingTotals,
    OrderTotals,
    _moscow_period_utc,
    inclusive_days,
    is_auth_sync_error,
    previous_period,
)


def test_previous_period_is_equal_length_and_does_not_overlap():
    start = date(2026, 9, 1)
    end = date(2026, 9, 10)

    assert inclusive_days(start, end) == 10
    previous_start, previous_end = previous_period(start, end)
    assert previous_start == date(2026, 8, 22)
    assert previous_end == date(2026, 8, 31)
    assert inclusive_days(previous_start, previous_end) == 10
    assert previous_end < start


def test_operational_date_boundaries_follow_wb_moscow_day():
    start, end_exclusive = _moscow_period_utc(
        date(2026, 9, 14), date(2026, 9, 14)
    )
    assert start == datetime(2026, 9, 13, 21, 0, tzinfo=timezone.utc)
    assert end_exclusive == datetime(2026, 9, 14, 21, 0, tzinfo=timezone.utc)


def test_permission_errors_are_not_misclassified_as_token_auth_errors():
    assert is_auth_sync_error("401 Unauthorized") is True
    assert is_auth_sync_error("Ошибка авторизации: подключение недействительно") is True
    assert is_auth_sync_error("403 Forbidden") is False
    assert (
        is_auth_sync_error(
            "У подключения нет доступа к категории WB API для advertising"
        )
        is False
    )


def test_ads_semantics_keep_attributed_and_total_orders_separate():
    advertising = AdvertisingTotals(
        views=1000,
        clicks=100,
        added_to_cart=40,
        orders=10,
        orders_amount=5000,
        spend=1000,
    )
    orders = OrderTotals(count=25, amount=12500, canceled_count=3)

    funnel = ads_handler._get_funnel_data(advertising, orders)
    acquisition = ads_handler._get_acquisition_cost_data(advertising, orders)

    assert funnel["ad_orders"] == 10
    assert funnel["ad_orders_amount"] == 5000
    assert funnel["total_orders"] == 25
    assert funnel["total_orders_amount"] == 12500
    assert acquisition["avg_order_value"] == 500
    assert acquisition["cpo"] == 100


@pytest.mark.asyncio
async def test_main_dashboard_uses_operational_orders_and_paid_funnel(monkeypatch):
    current_start = date(2026, 9, 1)
    current_end = date(2026, 9, 10)
    user_id = uuid4()

    async def fake_base(**kwargs):
        return SimpleNamespace(
            ordered_amount=999999,
            ordered_units=999,
            to_pay=600,
            logistics=30,
            storage_fee=10,
        )

    async def fake_sales(**kwargs):
        is_current = kwargs["start_date"] == current_start
        return SimpleNamespace(
            sales_amount=800 if is_current else 350,
            sales_units=8 if is_current else 4,
        )

    async def fake_returns(**kwargs):
        is_current = kwargs["start_date"] == current_start
        return SimpleNamespace(returns_amount=100 if is_current else 50)

    async def fake_unit(**kwargs):
        is_current = kwargs["start_date"] == current_start
        return {
            "total_profit": 200 if is_current else 100,
            "avg_margin_percent": 20,
            "avg_drr_percent": 10,
        }

    async def fake_orders(_session, _user_id, start_date, _end_date):
        if start_date == current_start:
            return OrderTotals(count=10, amount=1000, canceled_count=1)
        return OrderTotals(count=5, amount=400, canceled_count=1)

    async def fake_ads(_session, _user_id, _start_date, _end_date):
        return AdvertisingTotals(
            views=1000,
            clicks=100,
            added_to_cart=30,
            orders=7,
            orders_amount=700,
            spend=100,
        )

    monkeypatch.setattr(main_handler, "get_base_wb_report_stats", fake_base)
    monkeypatch.setattr(main_handler, "get_sales_wb_report_stats", fake_sales)
    monkeypatch.setattr(main_handler, "get_returns_wb_report_stats", fake_returns)
    monkeypatch.setattr(main_handler, "get_dashboard_unit_economy", fake_unit)
    monkeypatch.setattr(main_handler, "get_order_totals", fake_orders)
    monkeypatch.setattr(main_handler, "get_advertising_totals", fake_ads)

    result = await main_handler._calculate_stats(
        session=object(),
        user_id=user_id,
        start_date=current_start,
        end_date=current_end,
    )

    assert result["stats"]["ordered_units"]["value"] == 10
    assert result["stats"]["ordered_amount"]["value"] == 1000
    assert result["stats"]["avg_price"]["value"] == 100
    assert result["base_stats"]["orderedTotalCount"] == 10
    assert result["base_stats"]["adViews"] == 1000
    assert result["base_stats"]["clicks"] == 100
    assert result["base_stats"]["clicksPercentage"] == 10
    assert result["base_stats"]["addToCartPercentage"] == 30
    # Finance's legacy ordered_amount/units must not leak into the order KPI.
    assert result["stats"]["ordered_units"]["value"] != 999
