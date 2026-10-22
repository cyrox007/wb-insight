from decimal import Decimal

import pytest

from services.cost_price_service import _parse_cost


@pytest.mark.parametrize(
    "value",
    ["NaN", "sNaN", "Infinity", "-Infinity", float("nan"), float("inf")],
)
def test_cost_rejects_non_finite_values(value):
    with pytest.raises(ValueError, match="конечным числом"):
        _parse_cost(value)


@pytest.mark.parametrize(
    "value",
    ["10000000000000", "9999999999999.995", "1e40"],
)
def test_cost_rejects_numeric_overflow(value):
    with pytest.raises(ValueError, match="Себестоимость"):
        _parse_cost(value)


def test_cost_rejects_negative_and_invalid_values():
    with pytest.raises(ValueError, match="отрицательной"):
        _parse_cost("-0.01")
    with pytest.raises(ValueError, match="Некорректная"):
        _parse_cost("не число")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0", Decimal("0.00")),
        ("15.125", Decimal("15.12")),
        ("9999999999999.99", Decimal("9999999999999.99")),
    ],
)
def test_cost_accepts_finite_numeric_with_two_decimals(value, expected):
    assert _parse_cost(value) == expected
