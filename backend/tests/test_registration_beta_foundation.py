from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Response
from sqlalchemy.exc import IntegrityError

import handlers.auth_handler as auth_handler
from handlers.legal_handler import current_user_consents
from models.subscription_model import SubscriptionStatus
from services.subscription_service import create_demo_subscription


class RegistrationRequestStub:
    def __init__(self, payload: dict, *, user_id=None):
        self._payload = payload
        self.client = None
        self.headers = {}
        self.state = SimpleNamespace(
            user={"sub": str(user_id)} if user_id is not None else {}
        )

    async def json(self):
        return self._payload


class NestedTransactionStub:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        self.session.savepoint_enter_count += 1
        return self

    async def __aexit__(self, exc_type, _exc, _tb):
        if exc_type is None:
            self.session.savepoint_commit_count += 1
        else:
            self.session.savepoint_rollback_count += 1
        return False


class TransactionSessionStub:
    def __init__(self):
        self.rollback_count = 0
        self.savepoint_enter_count = 0
        self.savepoint_commit_count = 0
        self.savepoint_rollback_count = 0
        self.added = []
        self.flush_count = 0

    def begin_nested(self):
        return NestedTransactionStub(self)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        self.flush_count += 1

    async def rollback(self):
        self.rollback_count += 1


@pytest.mark.asyncio
async def test_registration_uses_savepoint_for_integrity_conflict(monkeypatch):
    session = TransactionSessionStub()
    request = RegistrationRequestStub(
        {"registrationData": {"entity_type": "individual", "legal_consents": []}}
    )
    response = Response()

    monkeypatch.setattr(auth_handler, "validate_consent_payload", lambda *_args, **_kwargs: ())

    async def fail_insert(*_args, **_kwargs):
        raise IntegrityError("insert user", {}, RuntimeError("duplicate"))

    monkeypatch.setattr(auth_handler, "insert_user", fail_insert)

    payload = await auth_handler.registration(request, response, session)

    assert response.status_code == 409
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "REGISTRATION_CONFLICT"
    assert session.rollback_count == 0
    assert session.savepoint_enter_count == 1
    assert session.savepoint_rollback_count == 1


@pytest.mark.asyncio
async def test_registration_rolls_back_savepoint_when_default_role_cannot_be_created(monkeypatch):
    session = TransactionSessionStub()
    request = RegistrationRequestStub(
        {"registrationData": {"entity_type": "individual", "legal_consents": []}}
    )
    response = Response()
    user = SimpleNamespace(id=uuid4())

    monkeypatch.setattr(auth_handler, "validate_consent_payload", lambda *_args, **_kwargs: ())

    async def insert_ok(*_args, **_kwargs):
        return user

    async def role_failed(*_args, **_kwargs):
        return False

    monkeypatch.setattr(auth_handler, "insert_user", insert_ok)
    monkeypatch.setattr(auth_handler, "create_user_role_association", role_failed)

    payload = await auth_handler.registration(request, response, session)

    assert response.status_code == 500
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert session.rollback_count == 0
    assert session.savepoint_enter_count == 1
    assert session.savepoint_rollback_count == 1


@pytest.mark.asyncio
async def test_registration_rolls_back_savepoint_when_demo_tariff_is_missing(monkeypatch):
    session = TransactionSessionStub()
    request = RegistrationRequestStub(
        {"registrationData": {"entity_type": "individual", "legal_consents": []}}
    )
    response = Response()
    user = SimpleNamespace(id=uuid4(), email="seller@example.com")

    monkeypatch.setattr(auth_handler, "validate_consent_payload", lambda *_args, **_kwargs: ())

    async def insert_ok(*_args, **_kwargs):
        return user

    async def role_ok(*_args, **_kwargs):
        return True

    async def record_ok(*_args, **_kwargs):
        return None

    async def missing_demo(*_args, **_kwargs):
        return None

    monkeypatch.setattr(auth_handler, "insert_user", insert_ok)
    monkeypatch.setattr(auth_handler, "create_user_role_association", role_ok)
    monkeypatch.setattr(auth_handler, "record_consents", record_ok)
    monkeypatch.setattr(auth_handler, "get_tariff_by_code", missing_demo)

    payload = await auth_handler.registration(request, response, session)

    assert response.status_code == 500
    assert payload["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert session.rollback_count == 0
    assert session.savepoint_enter_count == 1
    assert session.savepoint_rollback_count == 1


def test_registration_handler_does_not_use_manual_request_rollback():
    source = (
        Path(__file__).resolve().parents[1]
        / "handlers"
        / "auth_handler.py"
    ).read_text(encoding="utf-8")

    assert "db_session.rollback(" not in source
    assert "async with db_session.begin_nested():" in source


@pytest.mark.asyncio
async def test_demo_subscription_uses_canonical_lowercase_tariff_code():
    tariff_id = uuid4()

    class ResultStub:
        def scalar_one(self):
            return SimpleNamespace(id=tariff_id)

    class SessionStub:
        def __init__(self):
            self.query_params = None
            self.added = None
            self.flush_count = 0

        async def execute(self, statement):
            self.query_params = statement.compile().params
            return ResultStub()

        def add(self, value):
            self.added = value

        async def flush(self):
            self.flush_count += 1

    session = SessionStub()
    subscription = await create_demo_subscription(session, uuid4())

    assert "demo" in set(session.query_params.values())
    assert "DEMO" not in set(session.query_params.values())
    assert subscription.tariff_id == tariff_id
    assert subscription.status == SubscriptionStatus.DEMO
    assert session.added is subscription
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_own_consent_endpoint_does_not_expose_evidence_hmacs():
    user_id = uuid4()
    record = SimpleNamespace(
        id=uuid4(),
        user_id=user_id,
        document_code="terms",
        document_version="1.0-draft.1",
        document_sha256="a" * 64,
        context="registration",
        context_reference=str(user_id),
        accepted_at=datetime.now(timezone.utc),
        ip_hmac="secret-ip-evidence",
        user_agent_hmac="secret-user-agent-evidence",
    )

    class ScalarsStub:
        def all(self):
            return [record]

    class ResultStub:
        def scalars(self):
            return ScalarsStub()

    class SessionStub:
        async def execute(self, _statement):
            return ResultStub()

    request = RegistrationRequestStub({}, user_id=user_id)
    payload = await current_user_consents(request, SessionStub())

    assert payload["status"] == "success"
    assert len(payload["consents"]) == 1
    consent = payload["consents"][0]
    assert consent["document_code"] == "terms"
    assert "ip_hmac" not in consent
    assert "user_agent_hmac" not in consent



@pytest.mark.asyncio
async def test_registration_fails_closed_when_verification_transport_is_unavailable(monkeypatch):
    session = TransactionSessionStub()
    request = RegistrationRequestStub(
        {"registrationData": {"entity_type": "individual", "legal_consents": []}}
    )
    response = Response()
    insert_called = False

    async def fake_runtime(_session):
        return SimpleNamespace(ready=False)

    async def unexpected_insert(*_args, **_kwargs):
        nonlocal insert_called
        insert_called = True
        return None

    monkeypatch.setattr(auth_handler.lifecycle_config, "EMAIL_VERIFICATION_ENABLED", True)
    monkeypatch.setattr(auth_handler, "get_mail_transport_runtime", fake_runtime)
    monkeypatch.setattr(auth_handler, "insert_user", unexpected_insert)

    payload = await auth_handler.registration(request, response, session)

    assert response.status_code == 503
    assert payload["error"]["code"] == "EMAIL_VERIFICATION_DELIVERY_UNAVAILABLE"
    assert insert_called is False
