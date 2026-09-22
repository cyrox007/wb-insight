import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Response

from app import _handle_unexpected_exception, app
from handlers.dashboard import profile_handler
from services import token_services


class FailingDeleteSession:
    def __init__(self):
        self.deleted = None

    async def delete(self, token):
        self.deleted = token

    async def flush(self):
        raise RuntimeError("ошибка тестовой базы данных")


class FakeRequest:
    def __init__(self, user_id):
        self.state = SimpleNamespace(user={"sub": str(user_id)})


@pytest.mark.asyncio
async def test_delete_token_propagates_database_failure():
    session = FailingDeleteSession()
    token = object()

    with pytest.raises(RuntimeError, match="ошибка тестовой базы данных"):
        await token_services.delete_token(session, token)

    assert session.deleted is token


@pytest.mark.asyncio
async def test_profile_delete_does_not_swallow_transaction_failure(monkeypatch):
    user_id = uuid4()
    token_id = uuid4()
    token = SimpleNamespace(user_id=user_id)

    async def fake_get_token_by_id(_session, requested_token_id):
        assert requested_token_id == token_id
        return token

    async def fake_delete_token(_session, requested_token):
        assert requested_token is token
        raise RuntimeError("ошибка тестовой транзакции")

    monkeypatch.setattr(
        profile_handler,
        "get_token_by_id",
        fake_get_token_by_id,
    )
    monkeypatch.setattr(
        profile_handler,
        "delete_token",
        fake_delete_token,
    )

    with pytest.raises(RuntimeError, match="ошибка тестовой транзакции"):
        await profile_handler.delete_user_token(
            token_id,
            FakeRequest(user_id),
            Response(),
            db_session=object(),
        )


@pytest.mark.asyncio
async def test_unexpected_error_handler_returns_safe_russian_response():
    request = SimpleNamespace(
        method="DELETE",
        url=SimpleNamespace(path="/dashboard/profile/token/test"),
    )

    response = await _handle_unexpected_exception(
        request,
        RuntimeError("секретные внутренние детали"),
    )

    payload = json.loads(response.body)

    assert response.status_code == 500
    assert payload["status"] == "error"
    assert payload["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert payload["error"]["message"] == "Внутренняя ошибка сервера"
    assert "секретные внутренние детали" not in response.body.decode("utf-8")


def test_application_registers_unexpected_error_boundary():
    assert app.exception_handlers[Exception] is _handle_unexpected_exception
