from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from handlers.dashboard.finance_handler import router as finance_router
from models.wb_finance_summary import WbFinanceBalanceCurrent, WbFinanceReportSummary
from services.dashboard.finance_reconciliation import _delta, _matched
from services.payload_builder import build_payload_for_entity
from services.wb_finance_summary_service import (
    money,
    normalize_finance_report_summary,
    percentage,
)
from sync import process_finance_summary


def _unique_columns(model, constraint_name: str) -> list[str]:
    constraint = next(
        item
        for item in model.__table__.constraints
        if getattr(item, "name", None) == constraint_name
    )
    return list(constraint.columns.keys())


def _report(report_id: int) -> dict:
    return {
        "reportId": report_id,
        "sellerFinanceName": "ИП Тест",
        "dateFrom": "2026-09-01",
        "dateTo": "2026-09-07",
        "createDate": "2026-09-08",
        "currency": "RUB",
        "reportType": 1,
        "retailAmountSum": "10000.50",
        "forPaySum": "7000.25",
        "avgSalePercent": 12.3456,
        "deliveryServiceSum": "500.10",
        "paidStorageSum": "120.00",
        "paidAcceptanceSum": "25.00",
        "deductionSum": "30.00",
        "penaltySum": "10.00",
        "additionalPaymentSum": "15.00",
        "cashbackAmountSum": "2.00",
        "cashbackDiscountSum": "4.00",
        "cashbackCommissionChangeSum": "1.00",
        "paymentSchedule": "-5.00",
        "bankPaymentSum": "6330.15",
    }


def test_finance_summary_normalizes_current_wb_money_contract():
    user_id = uuid4()
    token_id = uuid4()
    observed_at = datetime(2026, 9, 15, tzinfo=timezone.utc)

    row = normalize_finance_report_summary(
        _report(307401554),
        user_id=user_id,
        token_id=token_id,
        observed_at=observed_at,
    )

    assert row["report_id"] == 307401554
    assert row["date_from"] == date(2026, 9, 1)
    assert row["date_to"] == date(2026, 9, 7)
    assert row["retail_amount_sum"] == Decimal("10000.50")
    assert row["for_pay_sum"] == Decimal("7000.25")
    assert row["bank_payment_sum"] == Decimal("6330.15")
    assert row["avg_sale_percent"] == Decimal("12.3456")
    assert money("1,25") == Decimal("1.25")
    assert percentage("6") == Decimal("6.0000")


def test_finance_summary_identity_is_account_scoped():
    assert _unique_columns(
        WbFinanceReportSummary,
        "uq_wb_finance_report_account_report",
    ) == ["token_id", "report_id"]
    assert _unique_columns(
        WbFinanceBalanceCurrent,
        "uq_wb_finance_balance_account",
    ) == ["token_id"]


def test_finance_payload_backfills_reports_and_details():
    details = build_payload_for_entity("realization", None)
    reports = build_payload_for_entity("finance_summary", None)

    today = date.today()
    assert (today - date.fromisoformat(details["dateFrom"])).days == 119
    assert details["period"] == "daily"
    assert reports["dateFrom"] == "2025-01-01"
    assert reports["period"] == "weekly"
    assert reports["offset"] == 0
    assert reports["balanceFetched"] is False


def test_reconciliation_uses_like_for_like_fields_with_small_tolerance():
    assert _delta(Decimal("100.01"), Decimal("100.00")) == 0.01
    assert _matched(0.01) is True
    assert _matched(-0.02) is True
    assert _matched(0.03) is False


def test_finance_dashboard_route_is_exposed():
    paths = {(route.path, method) for route in finance_router.routes for method in route.methods}
    assert ("/dashboard/finance/", "GET") in paths


@pytest.mark.asyncio
async def test_finance_summary_processor_resumes_offset_and_fetches_balance_once(monkeypatch):
    report_payloads = []
    saved_report_pages = []
    saved_balances = []
    checkpoints = []

    class FakeClient:
        responses = [[_report(1), _report(2)], [_report(3)]]
        balance_calls = 0

        def __init__(self, _token):
            self.responses = [list(page) for page in type(self).responses]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get_balance(self):
            type(self).balance_calls += 1
            return {"currency": "RUB", "current": 1000, "for_withdraw": 600}

        async def get_sales_reports_list(self, payload):
            report_payloads.append(dict(payload))
            return self.responses.pop(0)

    async def fake_balance(_session, **kwargs):
        saved_balances.append(kwargs["payload"])

    async def fake_reports(_session, **kwargs):
        saved_report_pages.append([item["reportId"] for item in kwargs["items"]])
        return len(kwargs["items"])

    async def fake_checkpoint(_session, job, payload):
        job.payload = dict(payload)
        checkpoints.append(dict(payload))

    class FakeSession:
        async def flush(self):
            return None

    monkeypatch.setattr(process_finance_summary, "WBFinanceClient", FakeClient)
    monkeypatch.setattr(process_finance_summary, "save_finance_balance", fake_balance)
    monkeypatch.setattr(process_finance_summary, "save_finance_report_summaries", fake_reports)
    monkeypatch.setattr(process_finance_summary, "persist_job_checkpoint", fake_checkpoint)

    job = SimpleNamespace(
        user_id=uuid4(),
        payload={
            "dateFrom": "2026-09-01",
            "dateTo": "2026-09-15",
            "limit": 2,
            "offset": 0,
            "period": "weekly",
            "balanceFetched": False,
        },
    )
    token = SimpleNamespace(id=uuid4())

    await process_finance_summary.process_finance_summary(FakeSession(), job, token)

    assert FakeClient.balance_calls == 1
    assert len(saved_balances) == 1
    assert [payload["offset"] for payload in report_payloads] == [0, 2]
    assert saved_report_pages == [[1, 2], [3]]
    assert checkpoints[0]["balanceFetched"] is True
    assert checkpoints[-1]["offset"] == 3
    assert job.payload["offset"] == 0
    assert job.payload["balanceFetched"] is False
