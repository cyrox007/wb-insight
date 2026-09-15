from datetime import date, datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from handlers.dashboard import ads_handler, main_handler
from services.dashboard import account_scope
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
    start, end_exclusive = _moscow_period_utc(date(2026, 9, 14), date(2026, 9, 14))
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


@pytest.mark.asyncio
async def test_dashboard_account_scope_uses_only_effective_allowed_tokens(monkeypatch):
    user_id = uuid4()
    allowed_id = uuid4()
    second_allowed_id = uuid4()
    foreign_or_unavailable_id = uuid4()

    async def fake_allowed(_session, requested_user_id):
        assert requested_user_id == user_id
        return [
            SimpleNamespace(id=allowed_id),
            SimpleNamespace(id=second_allowed_id),
        ]

    monkeypatch.setattr(account_scope, "get_allowed_wb_tokens", fake_allowed)

    aggregate_scope = await account_scope.resolve_dashboard_scope(
        object(), user_id, None
    )
    assert aggregate_scope.token_ids == (allowed_id, second_allowed_id)
    assert aggregate_scope.selected_token_id is None
    assert aggregate_scope.contains(allowed_id)
    assert aggregate_scope.contains(second_allowed_id)
    assert not aggregate_scope.contains(foreign_or_unavailable_id)

    selected_scope = await account_scope.resolve_dashboard_scope(
        object(), user_id, allowed_id
    )
    assert selected_scope.token_ids == (allowed_id,)
    assert selected_scope.selected_token_id == allowed_id

    with pytest.raises(account_scope.DashboardAccountUnavailableError):
        await account_scope.resolve_dashboard_scope(
            object(), user_id, foreign_or_unavailable_id
        )


@pytest.mark.asyncio
async def test_dashboard_account_scope_is_empty_without_tariff_access(monkeypatch):
    user_id = uuid4()

    async def fake_allowed(_session, requested_user_id):
        assert requested_user_id == user_id
        return []

    monkeypatch.setattr(account_scope, "get_allowed_wb_tokens", fake_allowed)
    scope = await account_scope.resolve_dashboard_scope(object(), user_id, None)
    assert scope.token_ids == ()
    assert scope.selected_token_id is None


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
async def test_main_dashboard_uses_one_account_scope_for_every_metric(monkeypatch):
    current_start = date(2026, 9, 1)
    current_end = date(2026, 9, 10)
    today = date(2026, 9, 14)
    user_id = uuid4()
    token_id = uuid4()
    scope = account_scope.DashboardAccountScope(
        token_ids=(token_id,),
        selected_token_id=token_id,
    )
    seen_scopes = []

    def scope_from_args(args, kwargs):
        resolved = kwargs.get("scope")
        if resolved is None and len(args) >= 5:
            resolved = args[4]
        seen_scopes.append(resolved)
        assert resolved is scope
        return resolved

    async def fake_base(*args, **kwargs):
        scope_from_args(args, kwargs)
        return SimpleNamespace(to_pay=600, logistics=30, storage_fee=10)

    async def fake_sales(*args, **kwargs):
        scope_from_args(args, kwargs)
        start = kwargs.get("start_date", args[2] if len(args) > 2 else None)
        current = start == current_start
        return SimpleNamespace(
            sales_amount=800 if current else 350,
            sales_units=8 if current else 4,
        )

    async def fake_returns(*args, **kwargs):
        scope_from_args(args, kwargs)
        start = kwargs.get("start_date", args[2] if len(args) > 2 else None)
        return SimpleNamespace(returns_amount=100 if start == current_start else 50)

    async def fake_unit(*args, **kwargs):
        scope_from_args(args, kwargs)
        start = kwargs.get("start_date", args[2] if len(args) > 2 else None)
        return {
            "total_profit": 200 if start == current_start else 100,
            "avg_margin_percent": 20,
            "avg_drr_percent": 10,
        }

    async def fake_orders(*args, **kwargs):
        scope_from_args(args, kwargs)
        start = kwargs.get("start_date", args[2] if len(args) > 2 else None)
        if start == current_start:
            return OrderTotals(count=10, amount=1000, canceled_count=1)
        return OrderTotals(count=5, amount=400, canceled_count=1)

    async def fake_ads(*args, **kwargs):
        scope_from_args(args, kwargs)
        return AdvertisingTotals(
            views=1000,
            clicks=100,
            added_to_cart=30,
            orders=7,
            orders_amount=700,
            spend=100,
        )

    async def fake_plan(*args, **kwargs):
        resolved = kwargs.get("scope")
        if resolved is None and len(args) >= 4:
            resolved = args[3]
        seen_scopes.append(resolved)
        assert resolved is scope
        return SimpleNamespace(
            revenue_target=3000.0,
            configured_accounts=1,
            total_accounts=1,
            complete=True,
        )

    monkeypatch.setattr(main_handler, "get_base_report_stats", fake_base)
    monkeypatch.setattr(main_handler, "get_sales_report_stats", fake_sales)
    monkeypatch.setattr(main_handler, "get_returns_report_stats", fake_returns)
    monkeypatch.setattr(
        main_handler, "get_dashboard_unit_economy_scoped", fake_unit
    )
    monkeypatch.setattr(main_handler, "get_order_totals", fake_orders)
    monkeypatch.setattr(main_handler, "get_advertising_totals", fake_ads)
    monkeypatch.setattr(main_handler, "get_monthly_plan_summary", fake_plan)

    result = await main_handler._calculate_stats(
        session=object(),
        user_id=user_id,
        start_date=current_start,
        end_date=current_end,
        scope=scope,
        today=today,
    )

    assert result["stats"]["ordered_units"]["value"] == 10
    assert result["stats"]["ordered_amount"]["value"] == 1000
    assert result["stats"]["avg_price"]["value"] == 100
    assert result["base_stats"]["orderedTotalCount"] == 10
    assert result["base_stats"]["adViews"] == 1000
    assert result["base_stats"]["clicks"] == 100
    assert result["base_stats"]["clicksPercentage"] == 10
    assert result["base_stats"]["addToCartPercentage"] == 30
    assert result["stats"]["fact_current_month"]["value"] == 700
    assert result["stats"]["plan_current_month"]["value"] == 3000
    assert result["stats"]["plan_current_month"]["complete"] is True
    assert seen_scopes
    assert all(item is scope for item in seen_scopes)
