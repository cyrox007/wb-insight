from datetime import date
from decimal import Decimal

import pytest

from handlers.dashboard.cost_price_handler import router as cost_router
from handlers.dashboard.expense_handler import router as expense_router
from models.manual_expense import ManualExpense
from models.product_cost_price_history import ProductCostPriceHistory
from services.cost_price_service import _parse_cost, _parse_effective_from
from services.manual_expense_service import parse_expense_amount


def test_cost_history_identity_is_date_effective_per_user_and_article():
    constraint = next(
        constraint
        for constraint in ProductCostPriceHistory.__table__.constraints
        if constraint.name == "uq_product_cost_history_user_nm_effective"
    )
    assert list(constraint.columns.keys()) == ["user_id", "nm_id", "effective_from"]


def test_manual_expenses_are_account_and_period_scoped():
    indexes = {tuple(index.columns.keys()) for index in ManualExpense.__table__.indexes}
    assert ("user_id", "date") in indexes
    assert ("token_id", "date") in indexes
    assert ("nm_id", "date") in indexes


def test_cost_versions_default_to_today_and_accept_backdated_effective_date(monkeypatch):
    assert _parse_effective_from("2026-08-15") == date(2026, 8, 15)
    assert _parse_effective_from(date(2026, 7, 1)) == date(2026, 7, 1)
    assert _parse_cost("123.456") == Decimal("123.46")

    with pytest.raises(ValueError):
        _parse_effective_from("not-a-date")
    with pytest.raises(ValueError):
        _parse_cost(-1)


def test_manual_expense_amount_is_positive_money():
    assert parse_expense_amount("50000") == Decimal("50000.00")
    assert parse_expense_amount("125.555") == Decimal("125.56")

    with pytest.raises(ValueError):
        parse_expense_amount(0)
    with pytest.raises(ValueError):
        parse_expense_amount(-10)
    with pytest.raises(ValueError):
        parse_expense_amount("bad")


def test_cost_and_expense_routers_expose_mutation_api():
    cost_paths = {(route.path, method) for route in cost_router.routes for method in route.methods}
    expense_paths = {(route.path, method) for route in expense_router.routes for method in route.methods}

    assert ("/cost-prices/batch", "POST") in cost_paths
    assert ("/cost-prices/upload", "POST") in cost_paths
    assert ("/cost-prices/{nm_id}", "DELETE") in cost_paths

    assert ("/dashboard/expenses/", "GET") in expense_paths
    assert ("/dashboard/expenses/", "POST") in expense_paths
    assert ("/dashboard/expenses/{expense_id}", "PUT") in expense_paths
    assert ("/dashboard/expenses/{expense_id}", "DELETE") in expense_paths
