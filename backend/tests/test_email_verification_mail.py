from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from models.mail_delivery import EmailVerificationToken, MailKind, MailStatus
from services import email_verification_service as verification
from services import mail_service


USER_ID = UUID("5cad7ec0-2b52-4d41-bccb-c47035fc73d1")


class _Result:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeSession:
    def __init__(self, results=None):
        self.results = list(results or [])
        self.added = []
        self.statements = []
        self.flushes = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return self.results.pop(0) if self.results else _Result()

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flushes += 1


async def _record_noop(_session, **_kwargs):
    return None


@pytest.mark.asyncio
async def test_verification_token_is_hash_only_and_bound_to_pending_email(monkeypatch):
    monkeypatch.setattr(verification.config, "EMAIL_VERIFICATION_TOKEN_TTL_MINUTES", 60)
    monkeypatch.setattr(verification, "record_lifecycle_event", _record_noop)
    user = SimpleNamespace(
        id=USER_ID,
        email="old@example.com",
        pending_email="new@example.com",
        email_verified_at=datetime.now(timezone.utc),
    )
    session = _FakeSession([_Result()])

    raw = await verification.issue_email_verification_token(
        session,
        user,
        email="NEW@example.com",
    )

    rows = [item for item in session.added if isinstance(item, EmailVerificationToken)]
    assert len(rows) == 1
    token = rows[0]
    assert token.email == "new@example.com"
    assert token.token_hash == verification.token_hash(raw)
    assert raw != token.token_hash
    assert "raw_token" not in EmailVerificationToken.__table__.columns
    assert "token" not in EmailVerificationToken.__table__.columns


@pytest.mark.asyncio
async def test_registration_verification_grants_demo_once(monkeypatch):
    now = datetime.now(timezone.utc)
    token = SimpleNamespace(
        id=uuid4(),
        user_id=USER_ID,
        email="seller@example.com",
        used_at=None,
        revoked_at=None,
        expires_at=now + timedelta(minutes=10),
    )
    user = SimpleNamespace(
        id=USER_ID,
        email="seller@example.com",
        pending_email=None,
        email_verified_at=None,
        is_active=True,
        session_version=1,
    )
    created = []

    async def create_demo(_session, user_id):
        created.append(user_id)
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(verification, "create_demo_subscription", create_demo)
    monkeypatch.setattr(verification, "record_lifecycle_event", _record_noop)
    session = _FakeSession([_Result(token), _Result(user), _Result(), _Result()])

    result = await verification.verify_email(session, "registration-secret")

    assert result is user
    assert user.email_verified_at is not None
    assert user.pending_email is None
    assert created == [USER_ID]
    assert token.used_at is not None


@pytest.mark.asyncio
async def test_email_change_requires_token_for_current_pending_target(monkeypatch):
    now = datetime.now(timezone.utc)
    token = SimpleNamespace(
        id=uuid4(),
        user_id=USER_ID,
        email="first-new@example.com",
        used_at=None,
        revoked_at=None,
        expires_at=now + timedelta(minutes=10),
    )
    user = SimpleNamespace(
        id=USER_ID,
        email="old@example.com",
        pending_email="second-new@example.com",
        email_verified_at=now - timedelta(days=30),
        is_active=True,
        session_version=8,
    )
    session = _FakeSession([_Result(token), _Result(user)])

    result = await verification.verify_email(session, "stale-secret")

    assert result is None
    assert user.email == "old@example.com"
    assert user.pending_email == "second-new@example.com"
    assert user.session_version == 8
    assert token.used_at is None


@pytest.mark.asyncio
async def test_verified_email_change_rotates_sessions_and_invalidates_reset_links(monkeypatch):
    now = datetime.now(timezone.utc)
    token = SimpleNamespace(
        id=uuid4(),
        user_id=USER_ID,
        email="new@example.com",
        used_at=None,
        revoked_at=None,
        expires_at=now + timedelta(minutes=10),
    )
    user = SimpleNamespace(
        id=USER_ID,
        email="old@example.com",
        pending_email="new@example.com",
        email_verified_at=now - timedelta(days=30),
        is_active=True,
        session_version=4,
    )
    events = []

    async def record(_session, **kwargs):
        events.append(kwargs["event_type"])
        return None

    monkeypatch.setattr(verification, "record_lifecycle_event", record)
    session = _FakeSession(
        [_Result(token), _Result(user), _Result(), _Result(), _Result()]
    )

    result = await verification.verify_email(session, "change-secret")

    assert result is user
    assert user.email == "new@example.com"
    assert user.pending_email is None
    assert user.email_verified_at is not None
    assert user.session_version == 5
    assert token.used_at is not None
    assert "email_changed" in events
    sql = "\n".join(str(statement) for statement in session.statements)
    assert "password_reset_tokens" in sql


@pytest.mark.asyncio
async def test_queued_password_reset_cannot_follow_old_email_after_identity_change():
    user = SimpleNamespace(
        id=USER_ID,
        email="new@example.com",
        pending_email=None,
        is_active=True,
        email_verified_at=datetime.now(timezone.utc),
    )
    message = SimpleNamespace(
        user_id=USER_ID,
        recipient_email="old@example.com",
        template_code="password_reset",
    )
    session = _FakeSession([_Result(user)])

    with pytest.raises(mail_service.PermanentMailDeliveryError) as exc_info:
        await mail_service._render_transactional(session, message)

    assert exc_info.value.code == "password_reset_target_stale"


@pytest.mark.asyncio
async def test_verification_mail_mints_token_for_exact_queue_recipient(monkeypatch):
    user = SimpleNamespace(
        id=USER_ID,
        email="old@example.com",
        pending_email="new@example.com",
        is_active=True,
        email_verified_at=datetime.now(timezone.utc),
    )
    message = SimpleNamespace(
        user_id=USER_ID,
        recipient_email="NEW@example.com",
        template_code="email_verification",
    )
    captured = {}

    async def issue(_session, _user, *, email=None):
        captured["email"] = email
        return "raw-secret"

    monkeypatch.setattr(mail_service, "issue_email_verification_token", issue)
    monkeypatch.setattr(mail_service.config, "EMAIL_VERIFICATION_BASE_URL", "https://app.company.test/verify-email")
    session = _FakeSession([_Result(user)])

    subject, body = await mail_service._render_transactional(session, message)

    assert captured["email"] == "new@example.com"
    assert "новый email" in subject.lower()
    assert "raw-secret" in body


@pytest.mark.asyncio
async def test_permanent_mail_failure_is_not_retried():
    message = SimpleNamespace(
        status=MailStatus.QUEUED.value,
        attempt_count=0,
        max_attempts=5,
        last_attempt_at=None,
        safe_error_code=None,
        next_attempt_at=datetime.now(timezone.utc),
    )
    session = _FakeSession([_Result(message)])

    result = await mail_service.mark_message_failure(
        session,
        uuid4(),
        "email_verification_target_stale",
        terminal=True,
    )

    assert result == MailStatus.FAILED.value
    assert message.status == MailStatus.FAILED.value
    assert message.attempt_count == message.max_attempts
    assert message.safe_error_code == "email_verification_target_stale"
