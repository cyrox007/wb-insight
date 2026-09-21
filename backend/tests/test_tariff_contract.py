from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Response

import handlers.control_panel.tariffs as tariff_handler
from services import tariff_service


def test_system_demo_code_is_case_insensitive():
    assert tariff_service.is_system_tariff(SimpleNamespace(code="demo"))
    assert tariff_service.is_system_tariff(SimpleNamespace(code="DEMO"))
    assert not tariff_service.is_system_tariff(SimpleNamespace(code="PRO"))


@pytest.mark.parametrize("limit_type", ["wb_accounts", "sync_frequency_hours"])
def test_required_runtime_limits_must_be_positive(limit_type):
    with pytest.raises(ValueError):
        tariff_service.validate_limit_value(limit_type, 0)

    tariff_service.validate_limit_value(limit_type, 1)


def test_optional_limits_allow_zero_but_never_negative():
    tariff_service.validate_limit_value("ai_queries_per_month", 0)

    with pytest.raises(ValueError):
        tariff_service.validate_limit_value("ai_queries_per_month", -1)


@pytest.mark.asyncio
async def test_missing_required_limits_are_reported(monkeypatch):
    async def fake_limits(_session, _tariff_id):
        return [SimpleNamespace(limit_type="wb_accounts", limit_value=1)]

    monkeypatch.setattr(tariff_service, "get_tariff_limits_by_id", fake_limits)

    missing = await tariff_service.get_missing_required_limits(object(), uuid4())

    assert missing == ["sync_frequency_hours"]


class RequestStub:
    def __init__(self, payload=None):
        self._payload = payload or {}

    async def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_system_demo_cannot_be_deactivated(monkeypatch):
    tariff = SimpleNamespace(id=uuid4(), code="demo", is_active=True, is_public=False)

    async def fake_get_tariff(_session, _tariff_id):
        return tariff

    monkeypatch.setattr(tariff_handler, "get_tariff_by_id", fake_get_tariff)

    response = Response()
    payload = await tariff_handler.update_tariff_status(
        str(tariff.id),
        RequestStub({"status": False}),
        response,
        object(),
    )

    assert response.status_code == 409
    assert payload["error"]["code"] == "SYSTEM_TARIFF_PROTECTED"


@pytest.mark.asyncio
async def test_system_demo_cannot_be_deleted(monkeypatch):
    tariff = SimpleNamespace(id=uuid4(), code="demo", is_active=True, is_public=False)

    async def fake_get_tariff(_session, _tariff_id):
        return tariff

    monkeypatch.setattr(tariff_handler, "get_tariff_by_id", fake_get_tariff)

    response = Response()
    payload = await tariff_handler.delete_tariff(tariff.id, response, object())

    assert response.status_code == 409
    assert payload["error"]["code"] == "SYSTEM_TARIFF_PROTECTED"


@pytest.mark.asyncio
async def test_required_limit_cannot_be_deleted_from_active_tariff(monkeypatch):
    tariff_id = uuid4()
    tariff = SimpleNamespace(id=tariff_id, code="PRO", is_active=True)
    limit = SimpleNamespace(
        tariff_id=tariff_id,
        limit_type="wb_accounts",
        limit_value=2,
    )

    async def fake_get_limit(*_args, **_kwargs):
        return limit

    async def fake_get_tariff(_session, _tariff_id):
        return tariff

    monkeypatch.setattr(tariff_handler, "get_limit", fake_get_limit)
    monkeypatch.setattr(tariff_handler, "get_tariff_by_id", fake_get_tariff)

    response = Response()
    payload = await tariff_handler.delete_tariff_limit(
        tariff_id,
        "wb_accounts",
        response,
        object(),
    )

    assert response.status_code == 409
    assert payload["error"]["code"] == "REQUIRED_TARIFF_LIMIT_PROTECTED"
