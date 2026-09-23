import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Response
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request

from handlers import email_verification_handler as handler
from services.email_verification_service import EmailVerificationTargetConflict


class _Result:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _NestedTransaction:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        self.session.savepoint_entries += 1
        return self

    async def __aexit__(self, exc_type, _exc, _tb):
        if exc_type is not None:
            self.session.savepoint_rollbacks += 1
        return False


class _Session:
    def __init__(self, execute_results=None):
        self.execute_results = list(execute_results or [])
        self.savepoint_entries = 0
        self.savepoint_rollbacks = 0
        self.rollback_called = False

    def begin_nested(self):
        return _NestedTransaction(self)

    async def execute(self, _statement):
        if self.execute_results:
            return self.execute_results.pop(0)
        return _Result()

    async def rollback(self):
        self.rollback_called = True
        raise AssertionError("Handler не должен выполнять ручной rollback")


def _request(path: str, payload):
    body = json.dumps(payload).encode("utf-8")
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": path,
            "headers": [(b"content-type", b"application/json")],
        },
        receive,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_kind", ["domain", "integrity"])
async def test_confirm_email_maps_conflict_to_409_inside_savepoint(monkeypatch, failure_kind):
    session = _Session()

    async def fake_verify(_session, _raw_token):
        if failure_kind == "domain":
            raise EmailVerificationTargetConflict("email_already_in_use")
        raise IntegrityError("UPDATE users", {}, RuntimeError("unique conflict"))

    monkeypatch.setattr(handler, "verify_email", fake_verify)

    response = Response()
    result = await handler.confirm_email(
        _request("/auth/email-verification/confirm", {"token": "test-token"}),
        response,
        session,
    )

    assert response.status_code == 409
    assert result["error"]["code"] == "EMAIL_ALREADY_EXISTS"
    assert session.savepoint_entries == 1
    assert session.savepoint_rollbacks == 1
    assert session.rollback_called is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        (["token"], "EMAIL_VERIFICATION_PAYLOAD_INVALID"),
        ({"token": "ok", "extra": True}, "EMAIL_VERIFICATION_FIELDS_UNSUPPORTED"),
        ({"token": ""}, "EMAIL_VERIFICATION_TOKEN_REQUIRED"),
        ({"token": "x" * 513}, "EMAIL_VERIFICATION_TOKEN_INVALID"),
    ],
)
async def test_confirm_email_rejects_invalid_payload_before_savepoint(payload, expected_code):
    session = _Session()
    response = Response()

    result = await handler.confirm_email(
        _request("/auth/email-verification/confirm", payload),
        response,
        session,
    )

    assert response.status_code == 400
    assert result["error"]["code"] == expected_code
    assert session.savepoint_entries == 0
    assert session.rollback_called is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        (["email"], "EMAIL_VERIFICATION_PAYLOAD_INVALID"),
        ({"email": "seller@example.com", "extra": True}, "EMAIL_VERIFICATION_FIELDS_UNSUPPORTED"),
        ({"email": "не-email"}, "EMAIL_INVALID"),
    ],
)
async def test_resend_email_rejects_invalid_payload(payload, expected_code, monkeypatch):
    async def fake_runtime(_session):
        return SimpleNamespace(ready=True)

    monkeypatch.setattr(handler, "get_mail_transport_runtime", fake_runtime)
    monkeypatch.setattr(handler.lifecycle_config, "EMAIL_VERIFICATION_ENABLED", True)

    response = Response()
    result = await handler.resend_email(
        _request("/auth/email-verification/resend", payload),
        response,
        _Session(),
    )

    assert response.status_code == 400
    assert result["error"]["code"] == expected_code


@pytest.mark.asyncio
async def test_resend_email_handles_zero_configured_interval_without_division_error(monkeypatch):
    user = SimpleNamespace(
        id=uuid4(),
        email="seller@example.com",
        is_active=True,
        email_verified_at=None,
    )
    queued = []

    async def fake_runtime(_session):
        return SimpleNamespace(ready=True)

    async def fake_get_user(_session, email):
        assert email == "seller@example.com"
        return user

    async def fake_queue(_session, **kwargs):
        queued.append(kwargs)
        return SimpleNamespace(id=uuid4())

    monkeypatch.setattr(handler, "get_mail_transport_runtime", fake_runtime)
    monkeypatch.setattr(handler, "get_user_by_email", fake_get_user)
    monkeypatch.setattr(handler, "queue_transactional_email", fake_queue)
    monkeypatch.setattr(handler.lifecycle_config, "EMAIL_VERIFICATION_ENABLED", True)
    monkeypatch.setattr(handler.lifecycle_config, "EMAIL_VERIFICATION_RESEND_SECONDS", 0)

    response = Response()
    result = await handler.resend_email(
        _request(
            "/auth/email-verification/resend",
            {"email": "  SELLER@Example.COM  "},
        ),
        response,
        _Session([_Result()]),
    )

    assert result["status"] == "success"
    assert len(queued) == 1
    assert queued[0]["recipient_email"] == "seller@example.com"


def test_email_verification_handler_uses_request_transaction_boundary():
    source = (
        Path(__file__).resolve().parents[1]
        / "handlers"
        / "email_verification_handler.py"
    ).read_text(encoding="utf-8")

    assert "db_session.rollback(" not in source
    assert "async with db_session.begin_nested()" in source
    assert 'tags=["Подтверждение email"]' in source
