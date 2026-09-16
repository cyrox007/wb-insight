from datetime import datetime, timezone
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


class TransactionSessionStub:
    def __init__(self):
        self.rollback_count = 0

    async def rollback(self):
        self.rollback_count += 1


@pytest.mark.asyncio
async def test_registration_rolls_back_integrity_conflict(monkeypatch):
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
    assert session.rollback_count == 1


@pytest.mark.asyncio
async def test_registration_rolls_back_when_default_role_cannot_be_created(monkeypatch):
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
    assert session.rollback_count == 1


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
