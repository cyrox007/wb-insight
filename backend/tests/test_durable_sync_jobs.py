from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from integrations.wildberries.client import WBAPIError, WBAuthError, WBRateLimitError
from models.sync_job_model import SyncJob
from services import sync_job_service
from tasks.processors import job_processor


class FakeResult:
    def __init__(self, *, jobs=None, job=None):
        self._jobs = jobs or []
        self._job = job

    def scalars(self):
        return self

    def all(self):
        return self._jobs

    def scalar_one_or_none(self):
        return self._job


class FakeSession:
    def __init__(self, result=None):
        self.result = result
        self.flushed = 0
        self.committed = 0

    async def execute(self, _stmt):
        return self.result

    async def flush(self):
        self.flushed += 1

    async def commit(self):
        self.committed += 1


def test_sync_job_model_has_durable_execution_fields():
    assert "attempt_count" in SyncJob.__table__.columns
    assert "available_at" in SyncJob.__table__.columns
    assert "lease_expires_at" in SyncJob.__table__.columns
    assert "ix_sync_jobs_pending_available" in {
        index.name for index in SyncJob.__table__.indexes
    }


@pytest.mark.asyncio
async def test_recover_stale_jobs_requeues_or_fails_by_retry_budget(monkeypatch):
    now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(sync_job_service.config, "SYNC_JOB_MAX_ATTEMPTS", 3)

    retryable = SimpleNamespace(
        id=uuid4(),
        status="processing",
        is_active=True,
        attempt_count=2,
        started_at=now - timedelta(minutes=40),
        finished_at=None,
        lease_expires_at=now - timedelta(minutes=5),
        available_at=now - timedelta(hours=1),
        error=None,
    )
    exhausted = SimpleNamespace(
        id=uuid4(),
        status="processing",
        is_active=True,
        attempt_count=3,
        started_at=now - timedelta(minutes=40),
        finished_at=None,
        lease_expires_at=now - timedelta(minutes=5),
        available_at=now - timedelta(hours=1),
        error=None,
    )
    session = FakeSession(FakeResult(jobs=[retryable, exhausted]))

    requeued, failed = await sync_job_service.recover_stale_jobs(
        session,
        now=now,
    )

    assert (requeued, failed) == (1, 1)
    assert retryable.status == "pending"
    assert retryable.is_active is True
    assert retryable.started_at is None
    assert retryable.lease_expires_at is None
    assert retryable.available_at == now
    assert exhausted.status == "failed"
    assert exhausted.is_active is False
    assert exhausted.finished_at == now
    assert exhausted.lease_expires_at is None
    assert session.flushed == 1


@pytest.mark.asyncio
async def test_claim_next_job_increments_attempt_and_sets_lease(monkeypatch):
    now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(sync_job_service.config, "SYNC_JOB_LEASE_SECONDS", 120)
    job = SimpleNamespace(
        status="pending",
        started_at=None,
        finished_at=now - timedelta(days=1),
        lease_expires_at=None,
        attempt_count=1,
        error="old",
    )
    session = FakeSession(FakeResult(job=job))

    claimed = await sync_job_service.claim_next_job(session, now=now)

    assert claimed is job
    assert job.status == "processing"
    assert job.attempt_count == 2
    assert job.started_at == now
    assert job.finished_at is None
    assert job.lease_expires_at == now + timedelta(seconds=120)
    assert job.error is None
    assert session.flushed == 1


@pytest.mark.asyncio
async def test_checkpoint_commits_cursor_and_renews_lease(monkeypatch):
    monkeypatch.setattr(sync_job_service.config, "SYNC_JOB_LEASE_SECONDS", 120)
    old_lease = datetime.now(timezone.utc) - timedelta(seconds=1)
    job = SimpleNamespace(payload={"rrdId": 0}, lease_expires_at=old_lease)
    session = FakeSession()

    await sync_job_service.persist_job_checkpoint(
        session,
        job,
        {"rrdId": 123},
    )

    assert job.payload == {"rrdId": 123}
    assert job.lease_expires_at > old_lease
    assert session.flushed == 1
    assert session.committed == 1


@pytest.mark.asyncio
async def test_retry_job_keeps_job_active_and_delays_next_claim(monkeypatch):
    now = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(sync_job_service.config, "SYNC_JOB_RETRY_BASE_SECONDS", 60)
    monkeypatch.setattr(sync_job_service.config, "SYNC_JOB_RETRY_MAX_SECONDS", 300)
    job = SimpleNamespace(
        attempt_count=2,
        status="processing",
        error=None,
        started_at=now,
        finished_at=None,
        lease_expires_at=now + timedelta(minutes=10),
        available_at=now,
        is_active=True,
    )
    session = FakeSession()

    await sync_job_service.retry_job(session, job, "temporary", now=now)

    assert job.status == "pending"
    assert job.is_active is True
    assert job.started_at is None
    assert job.lease_expires_at is None
    assert job.available_at == now + timedelta(seconds=120)
    assert job.error == "temporary"


def test_worker_auth_rejection_classification_is_explicit():
    assert job_processor._auth_error_rejects_credential(
        WBAuthError("rejected", endpoint="test", status_code=401)
    )
    assert not job_processor._auth_error_rejects_credential(
        WBAuthError("server config", endpoint="authorization")
    )


def test_worker_retry_classification_is_explicit():
    assert job_processor._is_retryable(
        WBRateLimitError("rate", endpoint="test", status_code=429)
    )
    assert job_processor._is_retryable(
        WBAPIError("server", endpoint="test", status_code=503)
    )
    assert job_processor._is_retryable(
        WBAPIError("transport", endpoint="test")
    )
    assert not job_processor._is_retryable(
        WBAPIError("bad request", endpoint="test", status_code=400)
    )
    assert not job_processor._is_retryable(
        WBAuthError("auth", endpoint="test", status_code=401)
    )
    assert not job_processor._is_retryable(
        job_processor.PermanentSyncJobError("invalid account")
    )
