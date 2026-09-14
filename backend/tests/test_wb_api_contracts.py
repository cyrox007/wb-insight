from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from integrations.wildberries.finance_normalizer import normalize_finance_row
from models.wb_product import WbProduct
from models.wb_report import WbRealizationReport
from models.wb_stock import WbStock
from services.payload_builder import build_payload_for_entity
from sync import process_products, process_realization, process_stock


def _unique_columns(model, constraint_name: str) -> list[str]:
    constraint = next(
        item
        for item in model.__table__.constraints
        if getattr(item, "name", None) == constraint_name
    )
    return list(constraint.columns.keys())


def test_payload_builder_uses_current_wb_contracts():
    cursor = datetime(2026, 9, 13, 12, 0, tzinfo=timezone.utc)

    finance = build_payload_for_entity("realization", cursor)
    assert finance["dateFrom"] == "2026-09-13"
    assert finance["limit"] == 100000
    assert finance["rrdId"] == 0
    assert "date_from" not in finance

    stocks = build_payload_for_entity("stocks", cursor)
    assert stocks == {
        "nmIds": [],
        "chrtIds": [],
        "limit": 250000,
        "offset": 0,
    }

    products = build_payload_for_entity("products", cursor)
    assert products["settings"]["cursor"] == {"limit": 100}
    assert products["settings"]["sort"] == {"ascending": True}


def test_finance_normalizer_maps_current_camel_case_contract():
    user_id = uuid4()
    account_id = uuid4()
    row = {
        "reportId": 987654321,
        "dateFrom": "2026-09-01",
        "dateTo": "2026-09-07",
        "createDate": "2026-09-08",
        "currency": "RUB",
        "reportType": 1,
        "rrdId": 1232610467,
        "giId": 123456,
        "subjectName": "Мини-печи",
        "nmId": 1234567,
        "brandName": "Brand",
        "vendorCode": "MAB123",
        "title": "Товар",
        "techSize": "0",
        "sku": "1231312352310",
        "docTypeName": "Продажа",
        "quantity": 1,
        "retailPrice": "1249.50",
        "retailAmount": "367.10",
        "salePercent": 5,
        "commissionPercent": 24,
        "officeName": "Коледино",
        "sellerOperName": "Продажа",
        "orderDt": "2026-09-03T00:00:00Z",
        "saleDt": "2026-09-05T00:00:00Z",
        "rrDate": "2026-09-05",
        "shkId": 1239159661,
        "retailPriceWithDisc": "399.68",
        "deliveryService": "42.50",
        "sellerPromo": "promo",
        "spp": 25.31,
        "kvwBase": 24.15,
        "kvw": 1.81,
        "supRatingUp": 0,
        "isKgvpV2": 0,
        "ppvzSalesCommission": "23.74",
        "forPay": "376.99",
        "ppvzReward": "0",
        "acquiringFee": "14.89",
        "acquiringBank": "Банк",
        "vw": "22.25",
        "vwNds": "4.45",
        "ppvzSupplierInn": "7700000000",
        "paidStorage": "3.20",
        "paidAcceptance": "1.10",
    }

    normalized = normalize_finance_row(row, user_id, account_id)

    assert normalized["user_id"] == user_id
    assert normalized["token_id"] == account_id
    assert normalized["rr_dt"].isoformat() == "2026-09-05"
    assert normalized["date_from"].isoformat() == "2026-09-01"
    assert normalized["date_to"].isoformat() == "2026-09-07"
    assert normalized["realization_report_id"] == 987654321
    assert normalized["sa_name"] == "MAB123"
    assert normalized["ts_name"] == "0"
    assert normalized["barcode"] == "1231312352310"
    assert normalized["retail_price"] == Decimal("1249.50")
    assert normalized["retail_price_with_disc_rub"] == Decimal("399.68")
    assert normalized["delivery_rub"] == Decimal("42.50")
    assert normalized["ppvz_for_pay"] == Decimal("376.99")
    assert normalized["storage_fee"] == Decimal("3.20")
    assert normalized["acceptance"] == Decimal("1.10")
    assert normalized["ppvz_inn"] == "7700000000"
    assert normalized["currency_name"] == "RUB"


def test_account_scoped_unique_keys_match_marketplace_rows():
    assert _unique_columns(WbRealizationReport, "uq_wb_realization_token_rrd") == [
        "token_id",
        "rrd_id",
    ]
    assert _unique_columns(WbStock, "uq_wb_stock_ui") == [
        "token_id",
        "nm_id",
        "chrt_id",
        "warehouse_id",
    ]
    assert _unique_columns(WbProduct, "uq_wb_product_account_nm") == [
        "token_id",
        "nm_id",
    ]


@pytest.mark.asyncio
async def test_finance_processor_follows_rrd_id_until_204(monkeypatch):
    payloads = []
    saved_pages = []

    class FakeClient:
        responses = [
            [{"rrdId": 10}, {"rrdId": 20}],
            [{"rrdId": 30}],
            [],
        ]

        def __init__(self, _token):
            self.responses = list(type(self).responses)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get_realization(self, payload):
            payloads.append(dict(payload))
            return self.responses.pop(0)

    async def fake_save(_session, _user_id, _account_id, page):
        saved_pages.append(list(page))

    monkeypatch.setattr(process_realization, "WBClient", FakeClient)
    monkeypatch.setattr(process_realization, "save_realization", fake_save)

    job = SimpleNamespace(
        payload={
            "dateFrom": "2026-09-01",
            "dateTo": "2026-09-07",
            "limit": 100000,
            "rrdId": 0,
        },
        user_id=uuid4(),
    )
    account = SimpleNamespace(id=uuid4())

    await process_realization.process_realization(object(), job, account)

    assert [payload["rrdId"] for payload in payloads] == [0, 20, 30]
    assert saved_pages == [
        [{"rrdId": 10}, {"rrdId": 20}],
        [{"rrdId": 30}],
    ]


@pytest.mark.asyncio
async def test_stock_processor_paginates_by_offset(monkeypatch):
    payloads = []
    saved = []

    class FakeClient:
        responses = [
            {"data": {"items": [{"nmId": 1}, {"nmId": 2}]}},
            {"data": {"items": [{"nmId": 3}]}},
        ]

        def __init__(self, _token):
            self.responses = list(type(self).responses)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get_stock(self, payload):
            payloads.append(dict(payload))
            return self.responses.pop(0)

    async def fake_save(_session, _user_id, _account_id, items):
        saved.extend(items)

    monkeypatch.setattr(process_stock, "WBClient", FakeClient)
    monkeypatch.setattr(process_stock, "save_stocks", fake_save)

    job = SimpleNamespace(payload={"limit": 2, "offset": 0}, user_id=uuid4())
    account = SimpleNamespace(id=uuid4())

    await process_stock.process_stock(object(), job, account)

    assert [payload["offset"] for payload in payloads] == [0, 2]
    assert [item["nmId"] for item in saved] == [1, 2, 3]


@pytest.mark.asyncio
async def test_product_processor_places_cursor_fields_at_wb_expected_level(monkeypatch):
    payloads = []

    class FakeClient:
        responses = [
            {
                "cards": [{"nmID": 1, "title": "A"}],
                "cursor": {
                    "updatedAt": "2026-09-14T10:00:00Z",
                    "nmID": 1,
                    "total": 100,
                },
            },
            {
                "cards": [{"nmID": 2, "title": "B"}],
                "cursor": {
                    "updatedAt": "2026-09-14T11:00:00Z",
                    "nmID": 2,
                    "total": 1,
                },
            },
        ]

        def __init__(self, _token):
            self.responses = list(type(self).responses)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get_products(self, payload):
            payloads.append(
                {
                    "settings": {
                        "cursor": dict(payload["settings"]["cursor"]),
                    }
                }
            )
            return self.responses.pop(0)

    async def fake_save(*_args, **_kwargs):
        return None

    monkeypatch.setattr(process_products, "WBClient", FakeClient)
    monkeypatch.setattr(process_products, "save_products", fake_save)

    job = SimpleNamespace(
        payload={
            "settings": {
                "sort": {"ascending": True},
                "cursor": {"limit": 100},
                "filter": {"withPhoto": -1},
            }
        },
        user_id=uuid4(),
    )
    account = SimpleNamespace(id=uuid4())

    await process_products.process_products(object(), job, account)

    assert payloads[0]["settings"]["cursor"] == {"limit": 100}
    assert payloads[1]["settings"]["cursor"] == {
        "limit": 100,
        "updatedAt": "2026-09-14T10:00:00Z",
        "nmID": 1,
    }
    assert "data" not in payloads[1]["settings"]["cursor"]
