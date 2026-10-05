from uuid import uuid4

import pandas as pd

from integrations.wildberries.finance_normalizer import normalize_finance_row
from services.dashboard.financial_semantics import _cost_coverage


def test_finance_normalizer_preserves_operation_without_article():
    user_id = uuid4()
    account_id = uuid4()

    row = normalize_finance_row(
        {
            "rrdId": 12345,
            "rrDate": "2026-10-01",
            "sellerOperName": "Логистика",
            "deliveryService": "300.00",
        },
        user_id,
        account_id,
    )

    assert row["nm_id"] == 0
    assert row["rrd_id"] == 12345
    assert row["supplier_oper_name"] == "Логистика"
    assert float(row["delivery_rub"]) == 300.0


def test_cost_coverage_is_evaluated_for_each_financial_operation():
    frame = pd.DataFrame(
        [
            {
                "nm_id": 101,
                "supplier_oper_name": "Продажа",
                "quantity": 1,
                "cost_known": False,
            },
            {
                "nm_id": 101,
                "supplier_oper_name": "Продажа",
                "quantity": 1,
                "cost_known": True,
            },
            {
                "nm_id": 0,
                "supplier_oper_name": "Логистика",
                "quantity": 0,
                "cost_known": False,
            },
        ]
    )

    complete, coverage, missing, with_cost, without_cost = _cost_coverage(frame)

    assert complete is False
    assert coverage == 50.0
    assert missing == 1
    assert with_cost == 0
    assert without_cost == 1


def test_unallocated_operation_does_not_create_false_cost_gap():
    frame = pd.DataFrame(
        [
            {
                "nm_id": 0,
                "supplier_oper_name": "Хранение",
                "quantity": 0,
                "cost_known": False,
            }
        ]
    )

    complete, coverage, missing, with_cost, without_cost = _cost_coverage(frame)

    assert complete is True
    assert coverage == 100.0
    assert missing == 0
    assert with_cost == 0
    assert without_cost == 0
