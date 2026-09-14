from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from integrations.wildberries import client as wb_client_module
from integrations.wildberries.client import WBClient, WBFeatureUnavailableError
from integrations.wildberries.funnel_normalizer import flatten_sales_funnel_history
from models.wb_sales_funnel import WbSalesFunnelDaily
from services.payload_builder import build_payload_for_entity
from sync import process_sales_funnel as funnel_processor
from sync.router import HANDLERS
from tasks.processors import job_processor
from tasks.schedulers.create_state_scheduler import ALL_ENTITIES


def test_sales_funnel_identity_is_account_scoped():
    constraint = next(
        constraint
        for constraint in WbSalesFunnelDaily.__table__.constraints
        if constraint.name == "uq_wb_sales_funnel_account_nm_date"
    )
    assert list(constraint.columns.keys()) == ["token_id", "nm_id", "date"]


def test_sales_funnel_v3_normalizer_preserves_daily_metrics():
    user_id = uuid4()
    token_id = uuid4()
    response = [
        {
            "product": {
                "nmId": 268913787,
                "title": "Кроссовки для бега",
                "vendorCode": "12345456",
                "brandName": "Demix",
                "subjectId": 105,
                "subjectName": "Кроссовки",
            },
            "history": [
                {
                    "date": "2026-09-10",
                    "openCount": 45,
                    "cartCount": 34,
                    "orderCount": 19,
                    "orderSum": 1262,
                    "buyoutCount": 17,
                    "buyoutSum": 1129.50,
                    "buyoutPercent": 89.47,
                    "addToCartConversion": 75.56,
                    "cartToOrderConversion": 55.88,
                    "addToWishlistCount": 3,
                }
            ],
            "currency": "rub",
        }
    ]

    rows = flatten_sales_funnel_history(response, user_id, token_id)

    assert len(rows) == 1
    row = rows[0]
    assert row["user_id"] == user_id
    assert row["token_id"] == token_id
    assert row["nm_id"] == 268913787
    assert row["date"] == date(2026, 9, 10)
    assert row["currency"] == "RUB"
    assert row["open_count"] == 45
    assert row["cart_count"] == 34
    assert row["order_count"] == 19
    assert row["order_sum"] == Decimal("1262")
    assert row["buyout_count"] == 17
    assert row["buyout_sum"] == Decimal("1129.5")
    assert row["buyout_percent"] == Decimal("89.47")
    assert row["add_to_cart_conversion"] == Decimal("75.56")
    assert row["cart_to_order_conversion"] == Decimal("55.88")
    assert row["add_to_wishlist_count"] == 3


def test_sales_funnel_payload_is_rolling_seven_day_window(monkeypatch):
    monkeypatch.setattr("services.payload_builder.config.WB_FUNNEL_LOOKBACK_DAYS", 7)
    payload = build_payload_for_entity("sales_funnel")
    start = date.fromisoformat(payload["selectedPeriod"]["start"])
    end = date.fromisoformat(payload["selectedPeriod"]["end"])

    assert (end - start).days == 6
    assert payload["nm_ids"] == []
    assert payload["nm_offset"] == 0


def test_sales_funnel_is_registered_in_sync_engine():
    assert "sales_funnel" in ALL_ENTITIES
    assert HANDLERS["sales_funnel"] is funnel_processor.process_sales_funnel


@pytest.mark.asyncio
async def test_sales_funnel_processor_batches_twenty_and_checkpoints(monkeypatch):
    token_id = uuid4()
    user_id = uuid4()
    token = SimpleNamespace(id=token_id)
    job = SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        token_id=token_id,
        payload={
            "selectedPeriod": {"start": "2026-09-08", "end": "2026-09-14"},
            "nm_ids": [],
            "nm_offset": 0,
        },
    )
    requested_batches = []
    checkpoints = []
    saved = []

    async def fake_account_nm_ids(_session, requested_token_id):
        assert requested_token_id == token_id
        return list(range(1001, 1046))

    class FakeClient:
        def __init__(self, requested_token):
            assert requested_token is token

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get_sales_funnel_history(self, payload):
            requested_batches.append(payload)
            return [
                {
                    "product": {"nmId": payload["nmIds"][0]},
                    "history": [{"date": "2026-09-14"}],
                    "currency": "RUB",
                }
            ]

    async def fake_save(_session, requested_user_id, requested_token_id, rows):
        saved.append((requested_user_id, requested_token_id, rows))
        return len(rows)

    async def fake_checkpoint(_session, requested_job, payload):
        assert requested_job is job
        checkpoints.append(dict(payload))
        job.payload = dict(payload)

    monkeypatch.setattr(funnel_processor, "_account_nm_ids", fake_account_nm_ids)
    monkeypatch.setattr(funnel_processor, "WBClient", FakeClient)
    monkeypatch.setattr(funnel_processor, "save_sales_funnel_history", fake_save)
    monkeypatch.setattr(funnel_processor, "persist_job_checkpoint", fake_checkpoint)
    monkeypatch.setattr(funnel_processor.config, "WB_FUNNEL_NM_BATCH_SIZE", 20)

    await funnel_processor.process_sales_funnel(object(), job, token)

    assert [len(call["nmIds"]) for call in requested_batches] == [20, 20, 5]
    assert all(call["aggregationLevel"] == "day" for call in requested_batches)
    assert all(call["skipDeletedNm"] is True for call in requested_batches)
    assert [checkpoint["nm_offset"] for checkpoint in checkpoints] == [20, 40, 45]
    assert checkpoints[-1]["nm_ids"] == list(range(1001, 1046))
    assert len(saved) == 3


class FakeRateLimiter:
    def __init__(self):
        self.acquired = []

    async def acquire(self, credential_id, endpoint, min_interval_seconds):
        self.acquired.append((credential_id, endpoint, min_interval_seconds))

    async def cooldown(self, *_args):
        return None

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_sales_funnel_402_is_typed_terminal_feature_error(monkeypatch):
    async def handler(request: httpx.Request):
        assert request.method == "POST"
        return httpx.Response(402, text="plan does not include this feature")

    token = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        encrypted_token="encrypted-placeholder",
    )
    limiter = FakeRateLimiter()
    monkeypatch.setattr(wb_client_module, "decrypt_token", lambda *_args: "raw-secret")

    client = WBClient(
        token,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        rate_limiter=limiter,
    )
    with pytest.raises(WBFeatureUnavailableError) as exc_info:
        await client.get_sales_funnel_history(
            {
                "selectedPeriod": {"start": "2026-09-08", "end": "2026-09-14"},
                "nmIds": [268913787],
                "skipDeletedNm": True,
                "aggregationLevel": "day",
            }
        )
    await client.aclose()

    assert exc_info.value.status_code == 402
    assert exc_info.value.endpoint == "analytics.sales_funnel_history"
    assert job_processor._is_retryable(exc_info.value) is False
    assert limiter.acquired[0][1] == "analytics.sales_funnel_history"
