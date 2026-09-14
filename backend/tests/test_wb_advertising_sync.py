from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from integrations.wildberries.advertising_normalizer import flatten_fullstats_v3
from integrations.wildberries.client import WBPermissionError
from models.tokens_model import Marketplace
from models.wb_advertising_stats import WbAdvertisingStats
from sync.process_advertising import _campaign_ids
from tasks.processors import job_processor


def test_advertising_fact_identity_is_account_scoped():
    index = next(
        index
        for index in WbAdvertisingStats.__table__.indexes
        if index.name == "idx_wb_adv_unique"
    )

    assert index.unique is True
    assert list(index.columns.keys()) == [
        "token_id",
        "campaign_id",
        "nm_id",
        "date",
        "platform_type",
    ]


def test_fullstats_v3_flattens_campaign_day_app_product_and_currency():
    user_id = uuid4()
    token_id = uuid4()
    campaigns = [
        {
            "advertId": 22161678,
            "currency": "rub",
            "boosterStats": [
                {"avg_position": 24, "date": "2026-09-10", "nm": 398309059}
            ],
            "days": [
                {
                    "date": "2026-09-10T00:00:00Z",
                    "apps": [
                        {
                            "appType": 32,
                            "nms": [
                                {
                                    "nmId": 398309059,
                                    "name": "Футболка",
                                    "views": 260,
                                    "clicks": 5,
                                    "ctr": 1.92,
                                    "cpc": 33.02,
                                    "sum": 165.10,
                                    "atbs": 1,
                                    "orders": 1,
                                    "canceled": 0,
                                    "cr": 20,
                                    "shks": 1,
                                    "sum_price": 500,
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    ]

    rows = flatten_fullstats_v3(campaigns, user_id, token_id)

    assert len(rows) == 1
    row = rows[0]
    assert row["user_id"] == user_id
    assert row["token_id"] == token_id
    assert row["campaign_id"] == 22161678
    assert row["nm_id"] == 398309059
    assert row["date"] == date(2026, 9, 10)
    assert row["platform_type"] == 32
    assert row["currency"] == "RUB"
    assert row["amount"] == Decimal("165.1")
    assert row["orders_amount"] == Decimal("500")
    assert row["avg_position"] == Decimal("24")
    assert row["canceled"] == 0


def test_campaign_discovery_keeps_active_and_recent_completed_only():
    response = {
        "adverts": [
            {"id": 101, "status": 9, "timestamps": {"updated": "2025-01-01"}},
            {"id": 102, "status": 11, "timestamps": {"updated": "2025-01-01"}},
            {
                "id": 103,
                "status": 7,
                "timestamps": {"updated": "2026-09-01T10:00:00+03:00"},
            },
            {
                "id": 104,
                "status": 7,
                "timestamps": {"updated": "2026-07-01T10:00:00+03:00"},
            },
            {"id": 105, "status": 8, "timestamps": {"updated": "2026-09-01"}},
        ]
    }

    assert _campaign_ids(response, date(2026, 8, 15)) == [101, 102, 103]


@pytest.mark.asyncio
async def test_promotion_permission_error_does_not_deactivate_wb_account(monkeypatch):
    user_id = uuid4()
    token_id = uuid4()
    job = SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        token_id=token_id,
        entity="advertising",
    )
    token = SimpleNamespace(
        id=token_id,
        user_id=user_id,
        marketplace=Marketplace.WILDBERRIES,
        is_valid=True,
        is_active=True,
    )
    state = SimpleNamespace(
        last_sync_at=None,
        last_success_at=None,
        last_error=None,
    )

    async def fake_get_token_by_id(_session, _token_id):
        return token

    async def fake_get_allowed_wb_tokens(_session, _user_id):
        return [token]

    async def fake_get_state(**_kwargs):
        return state

    async def fake_call_wb_api(**_kwargs):
        raise WBPermissionError(
            "promotion permission denied",
            endpoint="promotion.fullstats",
            status_code=403,
        )

    monkeypatch.setattr(job_processor, "get_token_by_id", fake_get_token_by_id)
    monkeypatch.setattr(job_processor, "get_allowed_wb_tokens", fake_get_allowed_wb_tokens)
    monkeypatch.setattr(job_processor, "get_state", fake_get_state)
    monkeypatch.setattr(job_processor, "call_wb_api", fake_call_wb_api)

    with pytest.raises(WBPermissionError):
        await job_processor.process_job(object(), job)

    assert token.is_active is True
    assert state.last_success_at is None


@pytest.mark.asyncio
async def test_permission_failure_is_terminal_for_entity_without_disabling_token(monkeypatch):
    token_id = uuid4()
    job = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        token_id=token_id,
        entity="advertising",
        attempt_count=1,
    )
    state = SimpleNamespace(last_sync_at=None, last_error=None)
    failed = {}

    async def fake_get_state(**_kwargs):
        return state

    async def fake_fail_job(_session, failed_job, error_text, now=None):
        failed["job"] = failed_job
        failed["error"] = error_text
        failed["now"] = now

    async def unexpected_get_token(*_args, **_kwargs):
        raise AssertionError("permission errors must not deactivate/fetch the credential")

    monkeypatch.setattr(job_processor, "get_state", fake_get_state)
    monkeypatch.setattr(job_processor, "fail_job", fake_fail_job)
    monkeypatch.setattr(job_processor, "get_token_by_id", unexpected_get_token)

    exc = WBPermissionError(
        "promotion permission denied",
        endpoint="promotion.fullstats",
        status_code=403,
    )
    await job_processor._record_failure(object(), job, exc)

    assert failed["job"] is job
    assert "promotion permission denied" in failed["error"]
    assert "нет доступа к категории WB API" in state.last_error
