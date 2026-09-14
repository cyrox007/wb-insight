from types import SimpleNamespace
from uuid import uuid4

import pytest

from models.sync_job_model import SyncJob
from models.tokens_model import Marketplace
from models.user_sync_state_model import UserSyncState
from services.sync_job_service import mark_jobs_processing
from tasks.processors import job_processor


def test_active_sync_job_uniqueness_is_account_scoped():
    index = next(index for index in SyncJob.__table__.indexes if index.name == "uq_job_active")

    assert index.unique is True
    assert list(index.columns.keys()) == ["token_id", "entity"]


def test_sync_state_uniqueness_separates_two_accounts():
    constraint = next(
        constraint
        for constraint in UserSyncState.__table__.constraints
        if constraint.name == "uq_sync_state"
    )

    assert list(constraint.columns.keys()) == ["user_id", "token_id", "entity"]


@pytest.mark.asyncio
async def test_processing_job_remains_active_until_final_status():
    class FakeSession:
        def __init__(self):
            self.flushed = False

        async def flush(self):
            self.flushed = True

    session = FakeSession()
    job = SimpleNamespace(status="pending", started_at=None, is_active=True)

    await mark_jobs_processing(session, [job])

    assert session.flushed is True
    assert job.status == "processing"
    assert job.started_at is not None
    assert job.is_active is True


@pytest.mark.asyncio
async def test_worker_processes_only_account_stored_on_job(monkeypatch):
    user_id = uuid4()
    token_a_id = uuid4()
    token_b_id = uuid4()
    job = SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        token_id=token_a_id,
        entity="stocks",
    )
    token_a = SimpleNamespace(
        id=token_a_id,
        user_id=user_id,
        marketplace=Marketplace.WILDBERRIES,
        is_valid=True,
        is_active=True,
    )
    token_b = SimpleNamespace(
        id=token_b_id,
        user_id=user_id,
        marketplace=Marketplace.WILDBERRIES,
        is_valid=True,
        is_active=True,
    )
    state = SimpleNamespace(
        last_sync_at=None,
        last_success_at=None,
        last_error="old error",
    )
    api_calls = []

    async def fake_get_token_by_id(_session, token_id):
        assert token_id == token_a_id
        return token_a

    async def fake_get_allowed_wb_tokens(_session, requested_user_id):
        assert requested_user_id == user_id
        return [token_a, token_b]

    async def fake_get_state(*, session, user_id, token_id, entity_code):
        assert user_id == job.user_id
        assert token_id == token_a_id
        assert entity_code == "stocks"
        return state

    async def fake_call_wb_api(*, session, token, job):
        api_calls.append(token.id)

    monkeypatch.setattr(job_processor, "get_token_by_id", fake_get_token_by_id)
    monkeypatch.setattr(job_processor, "get_allowed_wb_tokens", fake_get_allowed_wb_tokens)
    monkeypatch.setattr(job_processor, "get_state", fake_get_state)
    monkeypatch.setattr(job_processor, "call_wb_api", fake_call_wb_api)

    await job_processor.process_job(object(), job)

    assert api_calls == [token_a_id]
    assert state.last_sync_at is not None
    assert state.last_success_at is not None
    assert state.last_error is None


@pytest.mark.asyncio
async def test_worker_rejects_account_outside_tariff(monkeypatch):
    user_id = uuid4()
    token_a_id = uuid4()
    token_b_id = uuid4()
    job = SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        token_id=token_a_id,
        entity="stocks",
    )
    token_a = SimpleNamespace(
        id=token_a_id,
        user_id=user_id,
        marketplace=Marketplace.WILDBERRIES,
        is_valid=True,
        is_active=True,
    )
    token_b = SimpleNamespace(
        id=token_b_id,
        user_id=user_id,
        marketplace=Marketplace.WILDBERRIES,
        is_valid=True,
        is_active=True,
    )

    async def fake_get_token_by_id(_session, _token_id):
        return token_a

    async def fake_get_allowed_wb_tokens(_session, _user_id):
        return [token_b]

    monkeypatch.setattr(job_processor, "get_token_by_id", fake_get_token_by_id)
    monkeypatch.setattr(job_processor, "get_allowed_wb_tokens", fake_get_allowed_wb_tokens)

    with pytest.raises(RuntimeError, match="текущем тарифе"):
        await job_processor.process_job(object(), job)
