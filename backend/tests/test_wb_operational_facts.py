from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from integrations.wildberries.client import WBClient
from integrations.wildberries.operational_normalizer import (
    normalize_order_row,
    normalize_sale_row,
)
from models.tokens_model import Marketplace
from models.wb_operational import WbOrder, WbSale
from services.payload_builder import build_payload_for_entity
from settings import config
from sync import process_operational
from sync.router import HANDLERS
from tasks.processors import job_processor
from tasks.schedulers.create_state_scheduler import ALL_ENTITIES


def _unique_columns(model, name: str) -> list[str]:
    constraint = next(
        item
        for item in model.__table__.constraints
        if getattr(item, "name", None) == name
    )
    return list(constraint.columns.keys())


def test_order_normalizer_maps_operational_contract():
    user_id = uuid4()
    token_id = uuid4()
    row = {
        "date": "2026-09-14T12:00:00",
        "lastChangeDate": "2026-09-14T12:30:00",
        "warehouseName": "Коледино",
        "warehouseType": "Склад WB",
        "supplierArticle": "ART-1",
        "nmId": 123,
        "barcode": "460000000001",
        "totalPrice": "1299.90",
        "discountPercent": "10",
        "spp": "5.5",
        "finishedPrice": "1099.10",
        "priceWithDisc": "1169.91",
        "isCancel": True,
        "cancelDate": "2026-09-14T13:00:00",
        "srid": "order-srid-1",
    }

    normalized = normalize_order_row(row, user_id, token_id)

    assert normalized["user_id"] == user_id
    assert normalized["token_id"] == token_id
    assert normalized["srid"] == "order-srid-1"
    assert normalized["order_date"].isoformat() == "2026-09-14T09:00:00+00:00"
    assert normalized["last_change_date"].isoformat() == "2026-09-14T09:30:00+00:00"
    assert normalized["total_price"] == Decimal("1299.90")
    assert normalized["finished_price"] == Decimal("1099.10")
    assert normalized["is_cancel"] is True
    assert normalized["cancel_date"].isoformat() == "2026-09-14T10:00:00+00:00"


def test_sale_normalizer_keeps_sale_identity_and_preliminary_amounts():
    user_id = uuid4()
    token_id = uuid4()
    row = {
        "date": "2026-09-14T14:00:00",
        "lastChangeDate": "2026-09-14T14:05:00",
        "saleID": "S123456",
        "srid": "order-srid-1",
        "nmId": 123,
        "totalPrice": "1299.90",
        "paymentSaleAmount": "1150.00",
        "forPay": "820.55",
        "finishedPrice": "0",
        "priceWithDisc": "0",
    }

    normalized = normalize_sale_row(row, user_id, token_id)

    assert normalized["sale_id"] == "S123456"
    assert normalized["srid"] == "order-srid-1"
    assert normalized["payment_sale_amount"] == Decimal("1150.00")
    assert normalized["for_pay"] == Decimal("820.55")
    assert normalized["finished_price"] == Decimal("0")
    assert normalized["price_with_disc"] == Decimal("0")


def test_operational_fact_identity_is_account_scoped():
    assert _unique_columns(WbOrder, "uq_wb_order_account_srid") == [
        "token_id",
        "srid",
    ]
    assert _unique_columns(WbSale, "uq_wb_sale_account_sale_id") == [
        "token_id",
        "sale_id",
    ]


def test_operational_payload_prefers_durable_source_cursor():
    last_success = datetime(2026, 9, 1, tzinfo=timezone.utc)
    source_cursor = {"dateFrom": "2026-09-14T12:30:00"}

    orders = build_payload_for_entity("orders", last_success, source_cursor)
    sales = build_payload_for_entity("sales", last_success, source_cursor)

    assert orders == {"dateFrom": "2026-09-14T12:30:00", "flag": 0}
    assert sales == orders


def test_orders_and_sales_are_wired_into_scheduler_router_and_limiter():
    assert {"orders", "sales"}.issubset(set(ALL_ENTITIES))
    assert {"orders", "sales"}.issubset(set(HANDLERS))
    assert WBClient._endpoint_interval("statistics.orders") == config.WB_OPERATIONAL_MIN_INTERVAL_SECONDS
    assert WBClient._endpoint_interval("statistics.sales") == config.WB_OPERATIONAL_MIN_INTERVAL_SECONDS


@pytest.mark.asyncio
async def test_operational_processor_follows_last_change_date_and_checkpoints(monkeypatch):
    fetch_cursors = []
    checkpoints = []
    pages = [
        [
            {"lastChangeDate": "2026-09-14T10:01:00"},
            {"lastChangeDate": "2026-09-14T10:02:00"},
        ],
        [{"lastChangeDate": "2026-09-14T10:03:00"}],
        [],
    ]

    async def fetch(payload):
        fetch_cursors.append(payload["dateFrom"])
        return pages.pop(0)

    async def save(_session, _user_id, _token_id, rows):
        return len(rows)

    async def checkpoint(_session, job, payload):
        job.payload = dict(payload)
        checkpoints.append(dict(payload))

    monkeypatch.setattr(process_operational, "persist_job_checkpoint", checkpoint)

    job = SimpleNamespace(
        payload={"dateFrom": "2026-09-14T10:00:00", "flag": 0},
        user_id=uuid4(),
    )
    token = SimpleNamespace(id=uuid4())

    await process_operational._process_operational_feed(
        object(),
        job,
        token,
        entity="orders",
        fetch_page=fetch,
        save_page=save,
    )

    assert fetch_cursors == [
        "2026-09-14T10:00:00",
        "2026-09-14T10:02:00",
        "2026-09-14T10:03:00",
    ]
    assert [item["dateFrom"] for item in checkpoints] == [
        "2026-09-14T10:02:00",
        "2026-09-14T10:03:00",
    ]
    assert job.payload["dateFrom"] == "2026-09-14T10:03:00"


@pytest.mark.asyncio
async def test_operational_processor_stops_on_short_inclusive_boundary(monkeypatch):
    calls = 0

    async def fetch(_payload):
        nonlocal calls
        calls += 1
        return [{"lastChangeDate": "2026-09-14T10:00:00"}]

    async def save(_session, _user_id, _token_id, rows):
        return len(rows)

    async def checkpoint(_session, job, payload):
        job.payload = dict(payload)

    monkeypatch.setattr(process_operational, "persist_job_checkpoint", checkpoint)

    job = SimpleNamespace(
        payload={"dateFrom": "2026-09-14T10:00:00", "flag": 0},
        user_id=uuid4(),
    )
    token = SimpleNamespace(id=uuid4())

    await process_operational._process_operational_feed(
        object(),
        job,
        token,
        entity="sales",
        fetch_page=fetch,
        save_page=save,
    )

    assert calls == 1


@pytest.mark.asyncio
async def test_operational_processor_fails_closed_on_stalled_full_page(monkeypatch):
    async def fetch(_payload):
        return [
            {"lastChangeDate": "2026-09-14T10:00:00"},
            {"lastChangeDate": "2026-09-14T10:00:00"},
        ]

    async def save(_session, _user_id, _token_id, rows):
        return len(rows)

    async def checkpoint(_session, job, payload):
        job.payload = dict(payload)

    monkeypatch.setattr(process_operational, "OPERATIONAL_PAGE_LIMIT", 2)
    monkeypatch.setattr(process_operational, "persist_job_checkpoint", checkpoint)

    job = SimpleNamespace(
        payload={"dateFrom": "2026-09-14T10:00:00", "flag": 0},
        user_id=uuid4(),
    )
    token = SimpleNamespace(id=uuid4())

    with pytest.raises(RuntimeError, match="cursor stalled on a full page"):
        await process_operational._process_operational_feed(
            object(),
            job,
            token,
            entity="orders",
            fetch_page=fetch,
            save_page=save,
        )


@pytest.mark.asyncio
async def test_successful_operational_job_promotes_job_cursor_to_sync_state(monkeypatch):
    user_id = uuid4()
    token_id = uuid4()
    token = SimpleNamespace(
        id=token_id,
        user_id=user_id,
        marketplace=Marketplace.WILDBERRIES,
        is_valid=True,
    )
    job = SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        token_id=token_id,
        entity="orders",
        payload={"dateFrom": "2026-09-14T10:00:00", "flag": 0},
    )
    state = SimpleNamespace(
        last_sync_at=None,
        last_success_at=None,
        source_cursor={"dateFrom": "2026-09-14T09:00:00"},
        last_error="old",
    )

    async def fake_get_token_by_id(_session, requested_id):
        assert requested_id == token_id
        return token

    async def fake_allowed(_session, requested_user):
        assert requested_user == user_id
        return [token]

    async def fake_state(**_kwargs):
        return state

    async def fake_api(**kwargs):
        kwargs["job"].payload["dateFrom"] = "2026-09-14T10:30:00"

    monkeypatch.setattr(job_processor, "get_token_by_id", fake_get_token_by_id)
    monkeypatch.setattr(job_processor, "get_allowed_wb_tokens", fake_allowed)
    monkeypatch.setattr(job_processor, "get_state", fake_state)
    monkeypatch.setattr(job_processor, "call_wb_api", fake_api)

    await job_processor.process_job(object(), job)

    assert state.source_cursor == {"dateFrom": "2026-09-14T10:30:00"}
    assert state.last_success_at is not None
    assert state.last_error is None
