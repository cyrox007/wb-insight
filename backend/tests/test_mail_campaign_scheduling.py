from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from celery_app import celery_app
from integrations.mail.rusender import RuSenderAPIError
from models.mail_delivery import CampaignStatus, MailMessage, MailStatus
from services import mail_campaign_service as campaigns
from services import mail_service
from tasks.processors import mail_delivery


class _Rows:
    def __init__(self, rows=None):
        self._rows = list(rows or [])

    def all(self):
        return list(self._rows)


class _Session:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.added = []
        self.flushes = 0

    async def execute(self, _statement):
        return _Rows(self.rows)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flushes += 1


class _ScalarRows:
    def scalars(self):
        return self

    def all(self):
        return []


class _CaptureSession:
    def __init__(self):
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return _ScalarRows()


def _campaign(status=CampaignStatus.DRAFT.value):
    return SimpleNamespace(
        id=uuid4(),
        status=status,
        scheduled_at=None,
        completed_at=None,
        launched_at=None,
        segment={},
        subject="Тест",
        body="Сообщение",
        body_html="<p>Сообщение</p>",
        audience_count=0,
        queued_count=0,
        sent_count=0,
        failed_count=0,
        suppressed_count=0,
    )


def test_schedule_campaign_requires_future_timezone_aware_instant():
    now = datetime(2026, 9, 16, 18, 0, tzinfo=timezone.utc)
    campaign = _campaign()

    campaigns.schedule_campaign(campaign, now + timedelta(hours=2), now=now)

    assert campaign.status == CampaignStatus.SCHEDULED.value
    assert campaign.scheduled_at == now + timedelta(hours=2)

    with pytest.raises(ValueError, match="timezone"):
        campaigns.schedule_campaign(_campaign(), datetime(2026, 9, 17, 10, 0), now=now)
    with pytest.raises(ValueError, match="future"):
        campaigns.schedule_campaign(_campaign(), now, now=now)


def test_schedule_campaign_rejects_terminal_state():
    now = datetime(2026, 9, 16, 18, 0, tzinfo=timezone.utc)
    with pytest.raises(campaigns.CampaignStateConflict):
        campaigns.schedule_campaign(
            _campaign(CampaignStatus.COMPLETED.value),
            now + timedelta(hours=1),
            now=now,
        )


@pytest.mark.asyncio
async def test_launch_campaign_is_idempotent_for_existing_recipient(monkeypatch):
    user = SimpleNamespace(id=uuid4(), email="seller@example.com")
    campaign = _campaign(CampaignStatus.SCHEDULED.value)

    async def audience(_session, _segment):
        return [user]

    async def suppressions(_session, _users):
        return set(), set()

    monkeypatch.setattr(campaigns, "campaign_audience", audience)
    monkeypatch.setattr(campaigns, "suppressed_audience_keys", suppressions)

    first = _Session()
    await campaigns.launch_campaign(first, campaign)
    created = [item for item in first.added if isinstance(item, MailMessage)]
    assert len(created) == 1
    assert created[0].idempotency_key == f"campaign:{campaign.id}:{user.id}"
    assert created[0].body_html == "<p>Сообщение</p>"
    assert campaign.queued_count == 1
    assert campaign.status == CampaignStatus.QUEUED.value

    # Simulate an operational retry that sees the already materialized row.
    campaign.status = CampaignStatus.SCHEDULED.value
    campaign.scheduled_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    second = _Session(rows=[(user.id, MailStatus.QUEUED.value)])
    await campaigns.launch_campaign(second, campaign)

    assert second.added == []
    assert campaign.queued_count == 1
    assert campaign.status == CampaignStatus.QUEUED.value


@pytest.mark.asyncio
async def test_transactional_scan_excludes_campaign_rows_when_marketing_is_disabled():
    session = _CaptureSession()

    await mail_service.due_message_ids(session, include_marketing=False)

    sql = str(session.statement)
    assert "mail_messages.kind" in sql
    params = session.statement.compile().params
    assert "transactional" in params.values()


def test_mail_worker_preserves_safe_rusender_retry_code():
    error = RuSenderAPIError(
        "rusender_http_429",
        retryable=True,
        provider_error_code="rate_limit",
    )

    code, terminal = mail_delivery._delivery_failure(error)

    assert code == "rusender_http_429:rate_limit"
    assert terminal is False


def test_mail_worker_keeps_permanent_error_terminal():
    error = mail_service.PermanentMailDeliveryError("rusender_http_404")

    code, terminal = mail_delivery._delivery_failure(error)

    assert code == "rusender_http_404"
    assert terminal is True


def test_celery_beat_registers_campaign_scheduler():
    schedule = celery_app.conf.beat_schedule
    assert schedule["mail-campaign-scheduler"]["task"] == "mail.campaign.scan"
    assert schedule["mail-delivery"]["task"] == "mail.delivery.scan"
