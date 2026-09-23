import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Response
from starlette.requests import Request

from handlers.dashboard import profile_handler


class FakeSession:
    def __init__(self):
        self.flush_count = 0

    async def flush(self):
        self.flush_count += 1


class FakeEmailChangeSession:
    def __init__(self, recent_message_id=None):
        self.recent_message_id = recent_message_id

    async def execute(self, _query):
        recent_message_id = self.recent_message_id
        return SimpleNamespace(
            scalar_one_or_none=lambda: recent_message_id,
        )


def make_request(user_id, payload):
    body = json.dumps(payload).encode("utf-8")
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "PUT",
            "path": "/dashboard/profile/",
            "headers": [(b"content-type", b"application/json")],
        },
        receive,
    )
    request.state.user = {"sub": str(user_id)}
    return request


def make_user(user_id):
    return SimpleNamespace(
        id=user_id,
        full_name="Old Seller",
        email="seller@example.com",
        pending_email=None,
        phone="+79990000000",
        entity_type="individual",
        tax_rate=0.2,
        timezone="Europe/Moscow",
        is_active=True,
        roles=[],
        created_at=None,
    )


@pytest.mark.asyncio
async def test_profile_update_changes_formula_inputs(monkeypatch):
    user_id = uuid4()
    user = make_user(user_id)
    session = FakeSession()

    async def fake_get_user(_session, requested_user_id):
        assert requested_user_id == user_id
        return user

    monkeypatch.setattr(profile_handler, "get_user_by_uuid", fake_get_user)

    response = Response()
    result = await profile_handler.update_profile(
        make_request(
            user_id,
            {
                "full_name": "New Seller",
                "tax_rate": 0.06,
                "timezone": "Europe/Berlin",
            },
        ),
        response,
        session,
    )

    assert result["status"] == "success"
    assert user.full_name == "New Seller"
    assert user.entity_type == "individual"
    assert user.tax_rate == pytest.approx(0.06)
    assert user.timezone == "Europe/Berlin"
    assert result["user"]["tax_rate"] == pytest.approx(0.06)
    assert session.flush_count == 1





@pytest.mark.asyncio
async def test_profile_update_allows_same_entity_type_for_old_clients(monkeypatch):
    user_id = uuid4()
    user = make_user(user_id)
    session = FakeSession()

    async def fake_get_user(_session, _user_id):
        return user

    monkeypatch.setattr(profile_handler, "get_user_by_uuid", fake_get_user)

    response = Response()
    result = await profile_handler.update_profile(
        make_request(user_id, {"entity_type": "individual"}),
        response,
        session,
    )

    assert result["status"] == "success"
    assert user.entity_type == "individual"
    assert session.flush_count == 1


@pytest.mark.asyncio
async def test_profile_update_rejects_entity_type_change(monkeypatch):
    user_id = uuid4()
    user = make_user(user_id)
    session = FakeSession()

    async def fake_get_user(_session, _user_id):
        return user

    monkeypatch.setattr(profile_handler, "get_user_by_uuid", fake_get_user)

    response = Response()
    result = await profile_handler.update_profile(
        make_request(user_id, {"entity_type": "legal_entity"}),
        response,
        session,
    )

    assert response.status_code == 409
    assert result["error"]["code"] == "ENTITY_TYPE_CHANGE_REQUIRES_ADMIN"
    assert user.entity_type == "individual"
    assert session.flush_count == 0


@pytest.mark.asyncio
async def test_profile_update_rejects_non_object_payload(monkeypatch):
    user_id = uuid4()
    user = make_user(user_id)
    session = FakeSession()

    async def fake_get_user(_session, _user_id):
        return user

    monkeypatch.setattr(profile_handler, "get_user_by_uuid", fake_get_user)

    response = Response()
    result = await profile_handler.update_profile(
        make_request(user_id, ["not", "an", "object"]),
        response,
        session,
    )

    assert response.status_code == 400
    assert result["error"]["code"] == "PROFILE_PAYLOAD_INVALID"
    assert session.flush_count == 0


@pytest.mark.asyncio
async def test_profile_update_rejects_unsupported_fields(monkeypatch):
    user_id = uuid4()
    user = make_user(user_id)
    session = FakeSession()

    async def fake_get_user(_session, _user_id):
        return user

    monkeypatch.setattr(profile_handler, "get_user_by_uuid", fake_get_user)

    response = Response()
    result = await profile_handler.update_profile(
        make_request(user_id, {"inn": "7707083893"}),
        response,
        session,
    )

    assert response.status_code == 400
    assert result["error"]["code"] == "PROFILE_FIELDS_UNSUPPORTED"
    assert session.flush_count == 0


@pytest.mark.asyncio
async def test_profile_update_rejects_invalid_tax_rate(monkeypatch):
    user_id = uuid4()
    user = make_user(user_id)
    session = FakeSession()

    async def fake_get_user(_session, _user_id):
        return user

    monkeypatch.setattr(profile_handler, "get_user_by_uuid", fake_get_user)

    response = Response()
    result = await profile_handler.update_profile(
        make_request(user_id, {"tax_rate": 1.5}),
        response,
        session,
    )

    assert result["status"] == "error"
    assert result["error"]["code"] == "VALIDATION_ERROR"
    assert response.status_code == 400
    assert user.tax_rate == pytest.approx(0.2)
    assert session.flush_count == 0


def test_profile_router_exposes_settings_update():
    routes = {
        (route.path, method)
        for route in profile_handler.router.routes
        for method in route.methods
    }
    assert ("/dashboard/profile/", "GET") in routes
    assert ("/dashboard/profile/", "PUT") in routes
    assert ("/dashboard/profile/email-change/request", "POST") in routes
    assert ("/dashboard/profile/email-change/cancel", "POST") in routes



@pytest.mark.asyncio
async def test_email_change_request_queues_verification_without_plain_email_in_key(monkeypatch):
    user_id = uuid4()
    user = make_user(user_id)
    queued = {}
    lifecycle = {}

    async def fake_get_user(_session, _user_id):
        return user

    async def fake_get_by_email(_session, email):
        assert email == "new@example.com"
        return None

    async def fake_runtime(_session):
        return SimpleNamespace(ready=True)

    async def fake_queue(_session, **kwargs):
        queued.update(kwargs)
        return SimpleNamespace(id=uuid4())

    revoked = []

    async def fake_revoke(_session, requested_user_id):
        revoked.append(requested_user_id)

    async def fake_lifecycle(_session, **kwargs):
        lifecycle.update(kwargs)

    monkeypatch.setattr(profile_handler, "get_user_by_uuid", fake_get_user)
    monkeypatch.setattr(profile_handler, "get_user_by_uuid_for_update", fake_get_user)
    monkeypatch.setattr(profile_handler, "get_user_by_email", fake_get_by_email)
    monkeypatch.setattr(profile_handler, "get_mail_transport_runtime", fake_runtime)
    monkeypatch.setattr(profile_handler, "queue_transactional_email", fake_queue)
    monkeypatch.setattr(profile_handler, "revoke_email_verification_tokens", fake_revoke)
    monkeypatch.setattr(profile_handler, "record_lifecycle_event", fake_lifecycle)
    monkeypatch.setattr(
        profile_handler.lifecycle_config,
        "EMAIL_VERIFICATION_ENABLED",
        True,
    )
    monkeypatch.setattr(
        profile_handler.lifecycle_config,
        "EMAIL_VERIFICATION_RESEND_SECONDS",
        60,
    )

    response = Response()
    result = await profile_handler.request_email_change(
        make_request(user_id, {"email": "  NEW@Example.COM  "}),
        response,
        FakeEmailChangeSession(),
    )

    assert result["status"] == "success"
    assert result["pending_email"] == "new@example.com"
    assert result["queued"] is True
    assert user.pending_email == "new@example.com"
    assert queued["recipient_email"] == "new@example.com"
    assert queued["template_code"] == "email_verification"
    assert "new@example.com" not in queued["idempotency_key"]
    assert revoked == [user_id]
    assert lifecycle["event_type"] == "email_change_requested"
    assert lifecycle["event_data"] == {"verification_required": True}
    assert "email" not in lifecycle["event_data"]


@pytest.mark.asyncio
async def test_email_change_request_rejects_existing_email(monkeypatch):
    user_id = uuid4()
    user = make_user(user_id)
    other_user = SimpleNamespace(id=uuid4())

    async def fake_get_user(_session, _user_id):
        return user

    async def fake_get_by_email(_session, _email):
        return other_user

    async def fake_runtime(_session):
        return SimpleNamespace(ready=True)

    monkeypatch.setattr(profile_handler, "get_user_by_uuid", fake_get_user)
    monkeypatch.setattr(profile_handler, "get_user_by_uuid_for_update", fake_get_user)
    monkeypatch.setattr(profile_handler, "get_user_by_email", fake_get_by_email)
    monkeypatch.setattr(profile_handler, "get_mail_transport_runtime", fake_runtime)
    monkeypatch.setattr(
        profile_handler.lifecycle_config,
        "EMAIL_VERIFICATION_ENABLED",
        True,
    )

    response = Response()
    result = await profile_handler.request_email_change(
        make_request(user_id, {"email": "used@example.com"}),
        response,
        object(),
    )

    assert response.status_code == 409
    assert result["error"]["code"] == "EMAIL_ALREADY_EXISTS"
    assert user.pending_email is None


@pytest.mark.asyncio
async def test_email_change_request_requires_ready_verification_mail(monkeypatch):
    user_id = uuid4()
    user = make_user(user_id)

    async def fake_get_user(_session, _user_id):
        return user

    async def fake_runtime(_session):
        return SimpleNamespace(ready=False)

    monkeypatch.setattr(profile_handler, "get_user_by_uuid", fake_get_user)
    monkeypatch.setattr(profile_handler, "get_user_by_uuid_for_update", fake_get_user)
    monkeypatch.setattr(profile_handler, "get_mail_transport_runtime", fake_runtime)
    monkeypatch.setattr(
        profile_handler.lifecycle_config,
        "EMAIL_VERIFICATION_ENABLED",
        True,
    )

    response = Response()
    result = await profile_handler.request_email_change(
        make_request(user_id, {"email": "new@example.com"}),
        response,
        object(),
    )

    assert response.status_code == 503
    assert result["error"]["code"] == "EMAIL_CHANGE_DELIVERY_UNAVAILABLE"
    assert user.pending_email is None


@pytest.mark.asyncio
async def test_email_change_request_rejects_same_or_invalid_email(monkeypatch):
    user_id = uuid4()
    user = make_user(user_id)

    async def fake_get_user(_session, _user_id):
        return user

    async def fake_runtime(_session):
        return SimpleNamespace(ready=True)

    monkeypatch.setattr(profile_handler, "get_user_by_uuid", fake_get_user)
    monkeypatch.setattr(profile_handler, "get_user_by_uuid_for_update", fake_get_user)
    monkeypatch.setattr(profile_handler, "get_mail_transport_runtime", fake_runtime)
    monkeypatch.setattr(
        profile_handler.lifecycle_config,
        "EMAIL_VERIFICATION_ENABLED",
        True,
    )

    response = Response()
    same = await profile_handler.request_email_change(
        make_request(user_id, {"email": "SELLER@example.com"}),
        response,
        object(),
    )
    assert response.status_code == 400
    assert same["error"]["code"] == "EMAIL_UNCHANGED"

    response = Response()
    invalid = await profile_handler.request_email_change(
        make_request(user_id, {"email": "not-an-email"}),
        response,
        object(),
    )
    assert response.status_code == 400
    assert invalid["error"]["code"] == "EMAIL_INVALID"



@pytest.mark.asyncio
async def test_email_change_repeat_is_throttled_without_duplicate_mail_or_event(monkeypatch):
    user_id = uuid4()
    user = make_user(user_id)
    user.pending_email = "new@example.com"
    recent_message_id = uuid4()

    async def fake_get_user(_session, _user_id):
        return user

    async def fake_get_by_email(_session, _email):
        return None

    async def fake_runtime(_session):
        return SimpleNamespace(ready=True)

    async def fail_queue(*_args, **_kwargs):
        raise AssertionError("Повторный запрос не должен создавать второе письмо")

    async def fail_revoke(*_args, **_kwargs):
        raise AssertionError("Повторный запрос того же pending email не должен отзывать токены")

    async def fail_lifecycle(*_args, **_kwargs):
        raise AssertionError("Повторный запрос не должен создавать второе lifecycle-событие")

    monkeypatch.setattr(profile_handler, "get_user_by_uuid", fake_get_user)
    monkeypatch.setattr(profile_handler, "get_user_by_uuid_for_update", fake_get_user)
    monkeypatch.setattr(profile_handler, "get_user_by_email", fake_get_by_email)
    monkeypatch.setattr(profile_handler, "get_mail_transport_runtime", fake_runtime)
    monkeypatch.setattr(profile_handler, "queue_transactional_email", fail_queue)
    monkeypatch.setattr(profile_handler, "revoke_email_verification_tokens", fail_revoke)
    monkeypatch.setattr(profile_handler, "record_lifecycle_event", fail_lifecycle)
    monkeypatch.setattr(
        profile_handler.lifecycle_config,
        "EMAIL_VERIFICATION_ENABLED",
        True,
    )
    monkeypatch.setattr(
        profile_handler.lifecycle_config,
        "EMAIL_VERIFICATION_RESEND_SECONDS",
        60,
    )

    response = Response()
    result = await profile_handler.request_email_change(
        make_request(user_id, {"email": "new@example.com"}),
        response,
        FakeEmailChangeSession(recent_message_id),
    )

    assert result["status"] == "success"
    assert result["pending_email"] == "new@example.com"
    assert result["queued"] is False
    assert "уже было отправлено недавно" in result["message"]



@pytest.mark.asyncio
async def test_cancel_email_change_revokes_tokens_and_clears_pending(monkeypatch):
    user_id = uuid4()
    user = make_user(user_id)
    user.pending_email = "new@example.com"
    revoked = []
    lifecycle = {}

    async def fake_get_user(_session, _user_id):
        return user

    async def fake_revoke(_session, requested_user_id):
        revoked.append(requested_user_id)

    async def fake_lifecycle(_session, **kwargs):
        lifecycle.update(kwargs)

    monkeypatch.setattr(profile_handler, "get_user_by_uuid", fake_get_user)
    monkeypatch.setattr(profile_handler, "get_user_by_uuid_for_update", fake_get_user)
    monkeypatch.setattr(profile_handler, "revoke_email_verification_tokens", fake_revoke)
    monkeypatch.setattr(profile_handler, "record_lifecycle_event", fake_lifecycle)

    response = Response()
    result = await profile_handler.cancel_email_change(
        make_request(user_id, {}),
        response,
        object(),
    )

    assert result["status"] == "success"
    assert result["pending_email"] is None
    assert user.pending_email is None
    assert revoked == [user_id]
    assert lifecycle["event_type"] == "email_change_cancelled"
    assert lifecycle["event_data"] == {"verification_required": False}


@pytest.mark.asyncio
async def test_cancel_email_change_is_idempotent_without_pending(monkeypatch):
    user_id = uuid4()
    user = make_user(user_id)

    async def fake_get_user(_session, _user_id):
        return user

    async def fail_revoke(*_args, **_kwargs):
        raise AssertionError("Без pending email токены отзывать не нужно")

    monkeypatch.setattr(profile_handler, "get_user_by_uuid", fake_get_user)
    monkeypatch.setattr(profile_handler, "get_user_by_uuid_for_update", fake_get_user)
    monkeypatch.setattr(profile_handler, "revoke_email_verification_tokens", fail_revoke)

    response = Response()
    result = await profile_handler.cancel_email_change(
        make_request(user_id, {}),
        response,
        object(),
    )

    assert result["status"] == "success"
    assert result["pending_email"] is None
    assert "Ожидающей смены email нет" in result["message"]
