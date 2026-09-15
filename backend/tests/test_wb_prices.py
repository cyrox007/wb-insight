from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from integrations.wildberries import endpoints
from models.wb_price import WbPriceCurrent
from services.payload_builder import build_payload_for_entity
from services.wb_price_service import normalize_price_goods
from sync import process_prices
from tasks.schedulers.create_state_scheduler import ALL_ENTITIES


def _unique_columns(model, constraint_name: str) -> list[str]:
    constraint = next(
        item
        for item in model.__table__.constraints
        if getattr(item, "name", None) == constraint_name
    )
    return list(constraint.columns.keys())


def test_prices_use_current_wb_read_contract():
    assert endpoints.PRICES_LIST == (
        "https://discounts-prices-api.wildberries.ru/api/v2/list/goods/filter"
    )
    assert build_payload_for_entity("prices") == {"limit": 1000, "offset": 0}
    assert "prices" in ALL_ENTITIES
    assert _unique_columns(
        WbPriceCurrent,
        "uq_wb_price_current_account_nm_size",
    ) == ["token_id", "nm_id", "size_id"]


def test_price_normalizer_flattens_sizes_and_preserves_club_price():
    rows = normalize_price_goods(
        [
            {
                "nmID": 123,
                "vendorCode": "SKU-123",
                "currencyIsoCode4217": "RUB",
                "discount": 20,
                "clubDiscount": 5,
                "editableSizePrice": True,
                "isBadTurnover": False,
                "sizes": [
                    {
                        "sizeID": 1,
                        "techSizeName": "S",
                        "price": 1000,
                        "discountedPrice": 800,
                        "clubDiscountedPrice": 760,
                    },
                    {
                        "sizeID": 2,
                        "techSizeName": "M",
                        "price": "1200.50",
                        "discountedPrice": "960.40",
                        "clubDiscountedPrice": None,
                    },
                ],
            }
        ]
    )

    assert len(rows) == 2
    assert rows[0]["nm_id"] == 123
    assert rows[0]["size_id"] == 1
    assert rows[0]["base_price"] == Decimal("1000.00")
    assert rows[0]["discounted_price"] == Decimal("800.00")
    assert rows[0]["club_discounted_price"] == Decimal("760.00")
    assert rows[0]["discount"] == Decimal("20.00")
    assert rows[0]["club_discount"] == Decimal("5.00")
    assert rows[1]["base_price"] == Decimal("1200.50")
    assert rows[1]["club_discounted_price"] is None


def test_price_normalizer_skips_invalid_product_or_size_keys():
    rows = normalize_price_goods(
        [
            {"vendorCode": "missing-nm", "sizes": [{"sizeID": 1}]},
            {"nmID": 10, "sizes": [{"price": 100}]},
            {"nmID": 11, "sizes": "not-a-list"},
        ]
    )
    assert rows == []


@pytest.mark.asyncio
async def test_price_processor_resumes_with_one_snapshot_marker(monkeypatch):
    requested = []
    saved = []
    checkpoints = []
    pruned = []
    observed_at = datetime(2026, 9, 15, 9, 0, tzinfo=timezone.utc)

    class FakeClient:
        def __init__(self, _token):
            self.responses = [
                {"data": {"listGoods": [{"nmID": 1}, {"nmID": 2}]}},
                {"data": {"listGoods": [{"nmID": 3}]}},
            ]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get_prices(self, payload):
            requested.append(dict(payload))
            return self.responses.pop(0)

    async def fake_save(_session, *, user_id, token_id, items, observed_at):
        saved.append((user_id, token_id, list(items), observed_at))
        return len(items), 0

    async def fake_checkpoint(_session, job, payload):
        job.payload = dict(payload)
        checkpoints.append(dict(payload))

    async def fake_prune(_session, *, token_id, observed_at):
        pruned.append((token_id, observed_at))
        return 0

    monkeypatch.setattr(process_prices, "WBClient", FakeClient)
    monkeypatch.setattr(process_prices, "save_price_snapshot", fake_save)
    monkeypatch.setattr(process_prices, "persist_job_checkpoint", fake_checkpoint)
    monkeypatch.setattr(process_prices, "prune_price_snapshot", fake_prune)
    monkeypatch.setattr(
        process_prices,
        "snapshot_timestamp",
        lambda _value=None: observed_at,
    )

    token = SimpleNamespace(id=uuid4())
    job = SimpleNamespace(
        user_id=uuid4(),
        payload={"limit": 2, "offset": 0},
    )
    session = SimpleNamespace(flush=lambda: None)

    async def flush():
        return None

    session.flush = flush

    await process_prices.process_prices(session, job, token)

    assert requested == [
        {"limit": 2, "offset": 0},
        {"limit": 2, "offset": 2},
    ]
    assert len(saved) == 2
    assert all(call[3] == observed_at for call in saved)
    assert len(checkpoints) == 2
    assert checkpoints[0]["snapshotAt"] == observed_at.isoformat()
    assert checkpoints[1]["snapshotAt"] == observed_at.isoformat()
    assert pruned == [(token.id, observed_at)]
