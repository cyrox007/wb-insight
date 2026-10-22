from decimal import Decimal

import pytest

from services.manual_expense_service import parse_expense_amount


@pytest.mark.parametrize(
    "value",
    ["NaN", "sNaN", "Infinity", "-Infinity", float("nan"), float("inf")],
)
def test_expense_amount_rejects_non_finite_values(value):
    with pytest.raises(ValueError, match="конечным числом"):
        parse_expense_amount(value)


@pytest.mark.parametrize("value", ["0", "-0.01", "-12"])
def test_expense_amount_rejects_non_positive_values(value):
    with pytest.raises(ValueError, match="больше нуля"):
        parse_expense_amount(value)


@pytest.mark.parametrize("value", ["0.001", "0.004"])
def test_expense_amount_rejects_values_rounded_to_zero(value):
    with pytest.raises(ValueError, match="после округления"):
        parse_expense_amount(value)


@pytest.mark.parametrize("value", ["10000000000000000", "9999999999999999.995", "1e40"])
def test_expense_amount_rejects_overflow(value):
    with pytest.raises(ValueError, match="Сумма расхода"):
        parse_expense_amount(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0.01", Decimal("0.01")),
        ("15.125", Decimal("15.12")),
        ("9999999999999999.99", Decimal("9999999999999999.99")),
    ],
)
def test_expense_amount_accepts_valid_values(value, expected):
    assert parse_expense_amount(value) == expected
