from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from core import middleware
from core.authorization import require_admin
from core.lifecycle_config import lifecycle_config
from handlers import account_lifecycle_handler
from handlers.control_panel import users as control_panel_users
from models.account_lifecycle import PasswordResetToken
from models.subscription_model import SubscriptionStatus
from services import account_lifecycle_service as lifecycle
from utils.hashed_password import hash_password, verify_password
from utils.jwt import create_access_token


USER_ID = UUID("9da81db8-b89f-4aaf-9d9f-087c48b64e3c")
ADMIN_ID = UUID("41c426ee-f39c-4446-912b-615f1fc51f5f")


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
        self.rollbacks = 0

    async def execute(self, statement):
        self.statements.append(statement)
        return self.results.pop(0) if self.results else _Result()

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flushes += 1

    async def rollback(self):
        self.rollbacks += 1


def _request(path: str, *, method: str = "POST", body: bytes = b"{}", token: str | None = None):
    headers = [(b"content-type", b"application/json")]
    if token:
        headers.append((b"authorization", f"Bearer {token}".encode()))

    delivered = False

    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.request", "body": b"", "more_body": False}
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "https",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 1234),
            "server": ("test", 443),
        },
        receive=receive,
    )


@pytest.mark.asyncio
async def test_password_reset_token_is_random_and_only_digest_is_persisted(monkeypatch):
    monkeypatch.setattr(lifecycle.config, "PASSWORD_RESET_TOKEN_TTL_MINUTES", 30)
    session = _FakeSession([_Result()])
    user = SimpleNamespace(id=USER_ID)

    raw_token = await lifecycle.issue_password_reset_token(session, user)

    reset_rows = [item for item in session.added if item.__class__.__name__ == "PasswordResetToken"]
    assert len(reset_rows) == 1
    row = reset_rows[0]
    assert raw_token
    assert raw_token != row.token_hash
    assert len(row.token_hash) == 64
    assert row.token_hash == lifecycle._token_hash(raw_token)
    assert row.expires_at > datetime.now(timezone.utc)
    assert "token" not in PasswordResetToken.__table__.columns
    assert "raw_token" not in PasswordResetToken.__table__.columns


@pytest.mark.asyncio
async def test_password_reset_changes_password_and_revokes_prior_sessions():
    now = datetime.now(timezone.utc)
    reset_row = SimpleNamespace(
        user_id=USER_ID,
        used_at=None,
        expires_at=now + timedelta(minutes=10),
    )
    old_hash = hash_password("old-password")
    user = SimpleNamespace(
        id=USER_ID,
        is_active=True,
        session_version=4,
        hashed_password=old_hash,
    )
    session = _FakeSession([_Result(reset_row), _Result(user), _Result()])

    changed = await lifecycle.reset_password(
        session,
        raw_token="one-time-secret",
        new_password="new-password-123",
    )

    assert changed is user
    assert user.session_version == 5
    assert verify_password("new-password-123", user.hashed_password)
    assert not verify_password("old-password", user.hashed_password)
    assert len(session.statements) == 3


@pytest.mark.asyncio
async def test_soft_deactivation_revokes_sessions_credentials_and_identity_links(monkeypatch):
    monkeypatch.setattr(lifecycle.config, "ACCOUNT_DEACTIVATION_RETENTION_DAYS", 90)
    user = SimpleNamespace(
        id=USER_ID,
        is_active=True,
        session_version=7,
        pending_email="next@example.com",
        deactivated_at=None,
        deactivation_reason=None,
        retention_until=None,
    )
    session = _FakeSession()

    changed = await lifecycle.deactivate_account(
        session,
        user,
        actor_user_id=USER_ID,
        reason="user request",
    )

    assert changed is True
    assert user.is_active is False
    assert user.session_version == 8
    assert user.pending_email is None
    assert user.deactivated_at is not None
    assert user.deactivation_reason == "user request"
    assert user.retention_until > user.deactivated_at
    assert len(session.statements) == 4
    statement_sql = "\n".join(str(statement) for statement in session.statements)
    assert "password_reset_tokens" in statement_sql
    assert "email_verification_tokens" in statement_sql
    assert "api_tokens" in statement_sql
    assert "subscriptions" in statement_sql
    assert any(
        getattr(item, "event_type", None) == "account_deactivated"
        for item in session.added
    )


@pytest.mark.asyncio
async def test_paid_subscription_cancellation_keeps_current_period_access():
    period_end = datetime.now(timezone.utc) + timedelta(days=12)
    subscription = SimpleNamespace(
        id=uuid4(),
        current_period_end=period_end,
        cancel_at_period_end=False,
        cancel_requested_at=None,
        cancel_reason=None,
    )
    session = _FakeSession([_Result(subscription)])

    result = await lifecycle.request_subscription_cancellation(
        session,
        user_id=USER_ID,
        reason="not needed",
    )

    assert result is subscription
    assert subscription.cancel_at_period_end is True
    assert subscription.cancel_requested_at is not None
    assert subscription.current_period_end == period_end
    assert subscription.cancel_reason == "not needed"
    params = session.statements[0].compile().params
    assert SubscriptionStatus.ACTIVE in params.values()
    assert SubscriptionStatus.DEMO not in params.values()


@pytest.mark.asyncio
async def test_access_token_session_version_mismatch_is_rejected(monkeypatch):
    async def fake_state(_user_id):
        return True, 3

    monkeypatch.setattr(middleware, "_load_account_state", fake_state)
    token = create_access_token({"sub": str(USER_ID), "sv": 2})

    with pytest.raises(HTTPException) as exc_info:
        await middleware.auth_middle(_request("/dashboard", method="GET", token=token))

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail["error_type"] == "session_revoked"


@pytest.mark.asyncio
async def test_access_token_current_session_version_is_accepted(monkeypatch):
    async def fake_state(_user_id):
        return True, 3

    monkeypatch.setattr(middleware, "_load_account_state", fake_state)
    token = create_access_token({"sub": str(USER_ID), "sv": 3})
    request = _request("/dashboard", method="GET", token=token)

    await middleware.auth_middle(request)

    assert request.state.user["sub"] == str(USER_ID)
    assert request.state.user["sv"] == 3


@pytest.mark.asyncio
async def test_password_reset_request_does_not_disclose_account_existence(monkeypatch):
    monkeypatch.setattr(account_lifecycle_handler.lifecycle_config, "PASSWORD_RESET_ENABLED", True)

    async def missing_user(_session, _email):
        return None

    monkeypatch.setattr(account_lifecycle_handler, "get_user_by_email", missing_user)
    response = Response()
    request = _request(
        "/auth/password-reset/request",
        body=b'{"email":"unknown@example.com"}',
    )

    payload = await account_lifecycle_handler.request_password_reset(
        request,
        response,
        _FakeSession(),
    )

    assert payload["status"] == "success"
    assert "Если активный аккаунт" in payload["message"]


@pytest.mark.asyncio
async def test_password_reset_request_queues_transactional_mail_without_raw_token(monkeypatch):
    monkeypatch.setattr(account_lifecycle_handler.lifecycle_config, "PASSWORD_RESET_ENABLED", True)
    monkeypatch.setattr(account_lifecycle_handler.lifecycle_config, "EMAIL_VERIFICATION_ENABLED", False)
    user = SimpleNamespace(
        id=USER_ID,
        email="seller@example.com",
        is_active=True,
        email_verified_at=None,
    )
    queued = {}

    async def existing_user(_session, _email):
        return user

    async def queue(_session, **kwargs):
        queued.update(kwargs)
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(account_lifecycle_handler, "get_user_by_email", existing_user)
    monkeypatch.setattr(account_lifecycle_handler, "queue_transactional_email", queue)

    session = _FakeSession()
    payload = await account_lifecycle_handler.request_password_reset(
        _request(
            "/auth/password-reset/request",
            body=b'{"email":"seller@example.com"}',
        ),
        Response(),
        session,
    )

    assert payload["status"] == "success"
    assert queued["user"] is user
    assert queued["template_code"] == "password_reset"
    assert "token" not in queued
    assert session.rollbacks == 0


@pytest.mark.asyncio
async def test_support_event_is_allowlisted_and_attributed_to_admin(monkeypatch):
    target = SimpleNamespace(id=USER_ID)
    recorded = {}

    async def get_user(_session, user_id):
        assert user_id == USER_ID
        return target

    async def record(_session, **kwargs):
        recorded.update(kwargs)
        return SimpleNamespace(
            id=uuid4(),
            event_type=kwargs["event_type"],
            reference_id=kwargs["reference_id"],
            created_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(control_panel_users, "get_user_by_uuid", get_user)
    monkeypatch.setattr(control_panel_users, "record_lifecycle_event", record)
    request = _request(
        f"/control-panel/users/{USER_ID}/lifecycle-events",
        body=b'{"event_type":"support_payment_review","reason":"checked merchant statement","reference_id":"payment-42"}',
    )
    request.state.user_id = ADMIN_ID

    payload = await control_panel_users.add_support_lifecycle_event(
        USER_ID,
        request,
        Response(),
        _FakeSession(),
    )

    assert payload["status"] == "success"
    assert recorded["user_id"] == USER_ID
    assert recorded["actor_user_id"] == ADMIN_ID
    assert recorded["event_type"] == "support_payment_review"
    assert recorded["reference_id"] == "payment-42"
    assert recorded["event_data"] == {"source": "control_panel"}


@pytest.mark.asyncio
async def test_support_event_rejects_unbounded_event_type(monkeypatch):
    async def get_user(_session, _user_id):
        return SimpleNamespace(id=USER_ID)

    monkeypatch.setattr(control_panel_users, "get_user_by_uuid", get_user)
    request = _request(
        f"/control-panel/users/{USER_ID}/lifecycle-events",
        body=b'{"event_type":"arbitrary_database_action","reason":"no"}',
    )
    request.state.user_id = ADMIN_ID
    response = Response()

    payload = await control_panel_users.add_support_lifecycle_event(
        USER_ID,
        request,
        response,
        _FakeSession(),
    )

    assert response.status_code == 400
    assert payload["error"]["code"] == "INVALID_SUPPORT_EVENT_TYPE"


def test_control_panel_user_routes_have_explicit_admin_dependency():
    for route in control_panel_users.router.routes:
        dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
        assert require_admin in dependency_calls, route.path


def test_account_lifecycle_routes_are_registered():
    from app import app

    paths = app.openapi()["paths"]
    assert "post" in paths["/auth/password-reset/request"]
    assert "post" in paths["/auth/password-reset/confirm"]
    assert "post" in paths["/auth/email-verification/confirm"]
    assert "post" in paths["/auth/email-verification/resend"]
    assert "post" in paths["/account/email/change-request"]
    assert "delete" in paths["/account/email/change-request"]
    assert "post" in paths["/account/deactivate"]
    assert "post" in paths["/account/subscription/cancel"]
    assert "delete" in paths["/account/subscription/cancel"]
    assert "get" in paths["/control-panel/users/{user_uuid}/lifecycle-events"]
    assert "post" in paths["/control-panel/users/{user_uuid}/lifecycle-events"]


def test_production_password_reset_requires_https_when_enabled(monkeypatch):
    monkeypatch.setattr(lifecycle_config, "PASSWORD_RESET_ENABLED", True)
    monkeypatch.setattr(lifecycle_config, "PASSWORD_RESET_BASE_URL", "http://example.com/reset-password")
    monkeypatch.setattr(lifecycle_config, "SMTP_HOST", "smtp.company.test")
    monkeypatch.setattr(lifecycle_config, "SMTP_FROM_EMAIL", "no-reply@company.test")

    with pytest.raises(RuntimeError, match="https"):
        lifecycle_config.validate(production=True)
