from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import Response
from sqlalchemy.exc import IntegrityError

from handlers.control_panel import users as users_handler
from services.user_identity import (
    normalize_email,
    normalize_phone,
    validate_legal_identity,
)


TARGET_ID = UUID("22222222-2222-4222-8222-222222222222")
ACTOR_ID = UUID("11111111-1111-4111-8111-111111111111")


class RequestStub:
    def __init__(self, payload):
        self.payload = payload
        self.state = SimpleNamespace(user_id=str(ACTOR_ID), roles={"admin"})

    async def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


def target_user(**overrides):
    data = {
        "id": TARGET_ID,
        "full_name": "Пользователь",
        "email": "user@example.com",
        "phone": "+79991234567",
        "entity_type": "individual",
        "inn": "123456789012",
        "kpp": None,
        "legal_address": None,
        "tax_rate": 0.2,
        "timezone": "Europe/Moscow",
        "is_staff": False,
        "staff_id": None,
        "department": None,
        "position": None,
        "session_version": 1,
        "roles": [],
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class SessionStub:
    def __init__(self, *, fail_flush=False):
        self.fail_flush = fail_flush
        self.flush_count = 0
        self.refresh_count = 0

    @asynccontextmanager
    async def begin_nested(self):
        yield self

    async def flush(self):
        self.flush_count += 1
        if self.fail_flush:
            raise IntegrityError("UPDATE users", {}, RuntimeError("duplicate"))

    async def refresh(self, _target):
        self.refresh_count += 1


def test_shared_identity_normalizers_are_canonical():
    assert normalize_email("  User.Name@Example.COM  ") == "user.name@example.com"
    assert normalize_phone("8 (999) 123-45-67") == "+79991234567"
    assert normalize_phone("+7 999 123 45 67") == "+79991234567"


def test_legal_identity_contract_matches_registration_rules():
    legal = validate_legal_identity(
        entity_type="legal_entity",
        inn_value=" 7707083893 ",
        kpp_value="773601001",
        legal_address_value="  Москва  ",
    )
    assert legal == {
        "entity_type": "legal_entity",
        "inn": "7707083893",
        "kpp": "773601001",
        "legal_address": "Москва",
    }

    with pytest.raises(ValueError, match="10 цифр"):
        validate_legal_identity(
            entity_type="legal_entity",
            inn_value="123456789012",
            kpp_value="773601001",
            legal_address_value="Москва",
        )


@pytest.mark.asyncio
async def test_admin_edit_rejects_non_object_payload(monkeypatch):
    async def get_target(*_args, **_kwargs):
        return target_user()

    monkeypatch.setattr(users_handler, "get_user_by_uuid", get_target)

    response = Response()
    result = await users_handler.edit_user(
        TARGET_ID,
        RequestStub(["not", "object"]),
        response,
        SessionStub(),
    )

    assert response.status_code == 400
    assert result["error"]["code"] == "USER_UPDATE_PAYLOAD_INVALID"


@pytest.mark.asyncio
async def test_admin_edit_uses_canonical_phone_for_duplicate_check(monkeypatch):
    seen = {}

    async def get_target(*_args, **_kwargs):
        return target_user()

    async def get_phone(_session, phone):
        seen["phone"] = phone
        return SimpleNamespace(id=UUID("33333333-3333-4333-8333-333333333333"))

    monkeypatch.setattr(users_handler, "get_user_by_uuid", get_target)
    monkeypatch.setattr(users_handler, "get_user_by_phone", get_phone)

    response = Response()
    result = await users_handler.edit_user(
        TARGET_ID,
        RequestStub({"phone": "8 (999) 123-45-67"}),
        response,
        SessionStub(),
    )

    assert seen["phone"] == "+79991234567"
    assert response.status_code == 409
    assert result["error"]["code"] == "PHONE_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_admin_edit_rejects_invalid_legal_identity(monkeypatch):
    async def get_target(*_args, **_kwargs):
        return target_user()

    monkeypatch.setattr(users_handler, "get_user_by_uuid", get_target)

    response = Response()
    result = await users_handler.edit_user(
        TARGET_ID,
        RequestStub({
            "entity_type": "legal_entity",
            "inn": "123456789012",
            "legal_address": "Москва",
        }),
        response,
        SessionStub(),
    )

    assert response.status_code == 400
    assert result["error"]["code"] == "LEGAL_IDENTITY_INVALID"


@pytest.mark.asyncio
async def test_admin_edit_rejects_string_staff_flag(monkeypatch):
    async def get_target(*_args, **_kwargs):
        return target_user()

    monkeypatch.setattr(users_handler, "get_user_by_uuid", get_target)

    response = Response()
    result = await users_handler.edit_user(
        TARGET_ID,
        RequestStub({"is_staff": "false"}),
        response,
        SessionStub(),
    )

    assert response.status_code == 400
    assert result["error"]["code"] == "STAFF_FLAG_INVALID"


@pytest.mark.asyncio
async def test_admin_edit_canonicalizes_identity_and_rotates_session(monkeypatch):
    target = target_user(phone="+79990000000")

    async def get_target(*_args, **_kwargs):
        return target

    async def no_owner(*_args, **_kwargs):
        return None

    async def record_event(*_args, **_kwargs):
        return SimpleNamespace()

    monkeypatch.setattr(users_handler, "get_user_by_uuid", get_target)
    monkeypatch.setattr(users_handler, "get_user_by_phone", no_owner)
    monkeypatch.setattr(users_handler, "record_lifecycle_event", record_event)
    monkeypatch.setattr(users_handler, "_user_to_dict", lambda user: {"phone": user.phone})

    session = SessionStub()
    response = Response()
    result = await users_handler.edit_user(
        TARGET_ID,
        RequestStub({"phone": "8 (999) 123-45-67"}),
        response,
        session,
    )

    assert result["status"] == "success"
    assert result["user"]["phone"] == "+79991234567"
    assert target.session_version == 2
    assert session.flush_count == 1
    assert session.refresh_count == 1


@pytest.mark.asyncio
async def test_admin_edit_maps_concurrent_unique_conflict_to_409(monkeypatch):
    target = target_user()

    async def get_target(*_args, **_kwargs):
        return target

    async def record_event(*_args, **_kwargs):
        return SimpleNamespace()

    monkeypatch.setattr(users_handler, "get_user_by_uuid", get_target)
    monkeypatch.setattr(users_handler, "record_lifecycle_event", record_event)

    response = Response()
    result = await users_handler.edit_user(
        TARGET_ID,
        RequestStub({"full_name": "Новое имя"}),
        response,
        SessionStub(fail_flush=True),
    )

    assert response.status_code == 409
    assert result["error"]["code"] == "USER_IDENTITY_CONFLICT"
