from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from integrations.wildberries import client as wb_client_module
from integrations.wildberries.client import WBClient
from integrations.wildberries.paid_storage_normalizer import normalize_paid_storage_rows
from models.wb_paid_storage import WbPaidStorage
from services.payload_builder import build_payload_for_entity
from sync import process_paid_storage as storage_processor
from sync.router import HANDLERS
from tasks.schedulers.create_state_scheduler import ALL_ENTITIES


def test_paid_storage_normalizer_preserves_official_report_fields():
    user_id = uuid4()
    token_id = uuid4()
    rows = normalize_paid_storage_rows(
        [
            {
                "date": "2026-09-10",
                "logWarehouseCoef": 0,
                "officeId": 0,
                "warehouse": "Склад WB РФ",
                "warehouseCoef": 1.7,
                "giId": 123,
                "chrtId": 456,
                "size": "42",
                "barcode": "200000000001",
                "subject": "Кроссовки",
                "brand": "Brand",
                "vendorCode": "SKU-1",
                "nmId": 789,
                "volume": 1.25,
                "calcType": "короб",
                "warehousePrice": 42.35,
                "barcodesCount": 3,
                "palletPlaceCode": 0,
                "palletCount": 0.5,
                "originalDate": "2026-09-09",
                "loyaltyDiscount": 5.5,
                "tariffFixDate": "2026-09-01",
                "tariffLowerDate": "2026-09-20",
            }
        ],
        user_id,
        token_id,
        "task-1",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["user_id"] == user_id
    assert row["token_id"] == token_id
    assert row["source_task_id"] == "task-1"
    assert row["date"] == date(2026, 9, 10)
    assert row["nm_id"] == 789
    assert row["warehouse"] == "Склад WB РФ"
    assert row["warehouse_coef"] == Decimal("1.7")
    assert row["volume"] == Decimal("1.25")
    assert row["warehouse_price"] == Decimal("42.35")
    assert row["pallet_count"] == Decimal("0.5")
    assert row["original_date"] == date(2026, 9, 9)


def test_paid_storage_model_is_account_and_date_indexed():
    index_columns = {
        tuple(index.columns.keys()) for index in WbPaidStorage.__table__.indexes
    }
    assert ("token_id", "date") in index_columns
    assert ("user_id", "date") in index_columns
    assert ("nm_id", "date") in index_columns


def test_paid_storage_payload_initial_backfill_and_recent_refresh(monkeypatch):
    monkeypatch.setattr("services.payload_builder.config.WB_STORAGE_BACKFILL_DAYS", 30)
    monkeypatch.setattr("services.payload_builder.config.WB_STORAGE_REFRESH_DAYS", 8)

    initial = build_payload_for_entity("paid_storage")
    initial_start = date.fromisoformat(initial["dateFrom"])
    initial_end = date.fromisoformat(initial["dateTo"])
    assert (initial_end - initial_start).days == 29
    assert initial["currentDateFrom"] == initial["dateFrom"]
    assert initial["taskId"] is None

    recent = build_payload_for_entity(
        "paid_storage",
        source_cursor={"completedThrough": initial_end.isoformat()},
    )
    recent_start = date.fromisoformat(recent["dateFrom"])
    recent_end = date.fromisoformat(recent["dateTo"])
    assert (recent_end - recent_start).days == 7


def test_paid_storage_payload_catches_up_gaps_before_rolling_refresh(monkeypatch):
    monkeypatch.setattr("services.payload_builder.config.WB_STORAGE_REFRESH_DAYS", 8)
    current = build_payload_for_entity("paid_storage")
    end = date.fromisoformat(current["dateTo"])
    stale_cursor = end.replace(day=1) if end.day > 10 else end.fromordinal(end.toordinal() - 20)

    payload = build_payload_for_entity(
        "paid_storage",
        source_cursor={"completedThrough": stale_cursor.isoformat()},
    )
    assert date.fromisoformat(payload["dateFrom"]) == stale_cursor.fromordinal(
        stale_cursor.toordinal() + 1
    )


def test_paid_storage_is_registered_in_sync_engine():
    assert "paid_storage" in ALL_ENTITIES
    assert HANDLERS["paid_storage"] is storage_processor.process_paid_storage


@pytest.mark.asyncio
async def test_paid_storage_processor_splits_eight_day_chunks_and_checkpoints(monkeypatch):
    token_id = uuid4()
    user_id = uuid4()
    token = SimpleNamespace(id=token_id)
    job = SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        token_id=token_id,
        payload={
            "dateFrom": "2026-09-01",
            "dateTo": "2026-09-10",
            "currentDateFrom": "2026-09-01",
            "taskId": None,
            "taskDateFrom": None,
            "taskDateTo": None,
            "completedThrough": None,
        },
    )
    creates = []
    downloads = []
    replacements = []
    checkpoints = []

    class FakeClient:
        def __init__(self, requested_token):
            assert requested_token is token

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def create_paid_storage_report(self, payload):
            creates.append(dict(payload))
            return {"data": {"taskId": f"task-{len(creates)}"}}

        async def get_paid_storage_report_status(self, task_id):
            return {"data": {"id": task_id, "status": "done"}}

        async def download_paid_storage_report(self, task_id):
            downloads.append(task_id)
            return [{"date": "2026-09-01", "warehousePrice": 1}]

    async def fake_replace(_session, **kwargs):
        replacements.append(kwargs)
        return len(kwargs["data"])

    async def fake_checkpoint(_session, requested_job, payload):
        assert requested_job is job
        checkpoints.append(dict(payload))
        job.payload = dict(payload)

    monkeypatch.setattr(storage_processor, "WBClient", FakeClient)
    monkeypatch.setattr(storage_processor, "replace_paid_storage_period", fake_replace)
    monkeypatch.setattr(storage_processor, "persist_job_checkpoint", fake_checkpoint)

    await storage_processor.process_paid_storage(object(), job, token)

    assert creates == [
        {"dateFrom": "2026-09-01", "dateTo": "2026-09-08"},
        {"dateFrom": "2026-09-09", "dateTo": "2026-09-10"},
    ]
    assert downloads == ["task-1", "task-2"]
    assert [(item["start_date"], item["end_date"]) for item in replacements] == [
        (date(2026, 9, 1), date(2026, 9, 8)),
        (date(2026, 9, 9), date(2026, 9, 10)),
    ]
    # create checkpoint + completed chunk checkpoint for each WB task
    assert len(checkpoints) == 4
    assert checkpoints[0]["taskId"] == "task-1"
    assert checkpoints[1]["completedThrough"] == "2026-09-08"
    assert checkpoints[2]["taskId"] == "task-2"
    assert checkpoints[-1]["completedThrough"] == "2026-09-10"
    assert checkpoints[-1]["taskId"] is None


@pytest.mark.asyncio
async def test_paid_storage_processor_resumes_persisted_task_without_recreating(monkeypatch):
    token = SimpleNamespace(id=uuid4())
    job = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        token_id=token.id,
        payload={
            "dateFrom": "2026-09-01",
            "dateTo": "2026-09-08",
            "currentDateFrom": "2026-09-01",
            "taskId": "existing-task",
            "taskDateFrom": "2026-09-01",
            "taskDateTo": "2026-09-08",
        },
    )
    creates = []
    downloads = []

    class FakeClient:
        def __init__(self, _token):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def create_paid_storage_report(self, payload):
            creates.append(payload)
            raise AssertionError("resume must not create a new WB report task")

        async def get_paid_storage_report_status(self, task_id):
            assert task_id == "existing-task"
            return {"data": {"status": "done"}}

        async def download_paid_storage_report(self, task_id):
            downloads.append(task_id)
            return []

    async def fake_replace(*_args, **_kwargs):
        return 0

    async def fake_checkpoint(_session, _job, payload):
        job.payload = dict(payload)

    monkeypatch.setattr(storage_processor, "WBClient", FakeClient)
    monkeypatch.setattr(storage_processor, "replace_paid_storage_period", fake_replace)
    monkeypatch.setattr(storage_processor, "persist_job_checkpoint", fake_checkpoint)

    await storage_processor.process_paid_storage(object(), job, token)

    assert creates == []
    assert downloads == ["existing-task"]
    assert job.payload["completedThrough"] == "2026-09-08"


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
async def test_paid_storage_download_204_returns_empty_report(monkeypatch):
    async def handler(request: httpx.Request):
        assert request.method == "GET"
        assert request.url.path.endswith("/download")
        return httpx.Response(204)

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
    report = await client.download_paid_storage_report("task-1")
    await client.aclose()

    assert report == []
    assert limiter.acquired[0][1] == "analytics.paid_storage.download"
