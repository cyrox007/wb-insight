from decimal import Decimal

from handlers.dashboard.cost_price_handler import _parse_csv_cost_rows


def test_csv_preserves_exact_decimal_amount():
    rows = _parse_csv_cost_rows(
        "nm_id,cost_price,currency\n123,9999999999999.99,RUB\n"
    )
    assert len(rows) == 1
    assert rows[0]["cost_price"] == Decimal("9999999999999.99")


def test_csv_rejects_non_finite_and_overflow_values():
    rows = _parse_csv_cost_rows(
        "nm_id,cost_price\n123,NaN\n124,Infinity\n"
        "125,-1\n126,10000000000000\n127,15.125\n"
    )
    assert len(rows) == 1
    assert rows[0]["nm_id"] == 127
    assert rows[0]["cost_price"] == Decimal("15.12")


def test_csv_keeps_zero_cost_and_skips_invalid_sku():
    rows = _parse_csv_cost_rows(
        "nm_id,cost_price\n0,50\n123,0\n"
    )
    assert rows == [
        {
            "nm_id": 123,
            "seller_sku": None,
            "product_name": None,
            "cost_price": Decimal("0.00"),
            "currency": "RUB",
            "comment": None,
            "effective_from": None,
        }
    ]
