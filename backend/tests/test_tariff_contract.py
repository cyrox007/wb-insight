from pathlib import Path
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


@pytest.mark.asyncio
async def test_public_catalog_hides_incomplete_tariffs(monkeypatch):
    ready = SimpleNamespace(id=uuid4(), code="PRO")
    incomplete = SimpleNamespace(id=uuid4(), code="STARTER")

    async def fake_list(_session, **_kwargs):
        return [ready, incomplete]

    async def fake_missing(_session, tariff_id):
        return [] if tariff_id == ready.id else ["sync_frequency_hours"]

    monkeypatch.setattr(tariff_service, "get_tariffs_list", fake_list)
    monkeypatch.setattr(tariff_service, "get_missing_required_limits", fake_missing)

    result = await tariff_service.get_public_runtime_ready_tariffs(object())

    assert result == [ready]


@pytest.mark.asyncio
async def test_service_refuses_system_tariff_delete(monkeypatch):
    demo = SimpleNamespace(id=uuid4(), code="demo")

    async def fake_get(_session, _tariff_id):
        return demo

    monkeypatch.setattr(tariff_service, "get_tariff_by_id", fake_get)

    deleted = await tariff_service.delete_tariff_by_id(object(), demo.id)

    assert deleted is False



class FailingTariffSession:
    def __init__(self):
        self.added = None
        self.rollback_called = False

    def add(self, value):
        self.added = value

    async def flush(self):
        raise RuntimeError("секретная ошибка тестовой базы")

    async def rollback(self):
        self.rollback_called = True


@pytest.mark.asyncio
async def test_tariff_service_propagates_database_failure_without_local_rollback():
    session = FailingTariffSession()

    with pytest.raises(RuntimeError, match="секретная ошибка тестовой базы"):
        await tariff_service.insert_tariff(
            session,
            {
                "code": "PRO",
                "name": "Pro",
                "description": "",
                "price_rub": 100,
                "is_active": False,
                "is_public": False,
            },
        )

    assert session.added is not None
    assert session.rollback_called is False


@pytest.mark.asyncio
async def test_tariff_handler_propagates_database_failure(monkeypatch):
    tariff_id = uuid4()
    tariff = SimpleNamespace(
        id=tariff_id,
        code="PRO",
        name="Pro",
        description="",
        price_rub=100,
        is_active=False,
        is_public=False,
    )

    async def fake_get_tariff(_session, _tariff_id):
        return tariff

    async def fake_update_tariff(*_args, **_kwargs):
        raise RuntimeError("секретная ошибка изменения тарифа")

    monkeypatch.setattr(tariff_handler, "get_tariff_by_id", fake_get_tariff)
    monkeypatch.setattr(tariff_handler, "update_tariff", fake_update_tariff)

    with pytest.raises(RuntimeError, match="секретная ошибка изменения тарифа"):
        await tariff_handler.edit_tariff(
            tariff_id,
            RequestStub({"name": "Новое имя"}),
            Response(),
            object(),
        )


@pytest.mark.asyncio
async def test_duplicate_tariff_code_returns_conflict_before_insert(monkeypatch):
    existing = SimpleNamespace(id=uuid4(), code="PRO")
    insert_called = False

    async def fake_get_by_code(_session, code):
        assert code == "PRO"
        return existing

    async def fake_insert(*_args, **_kwargs):
        nonlocal insert_called
        insert_called = True
        return None

    monkeypatch.setattr(tariff_handler, "get_tariff_by_code", fake_get_by_code)
    monkeypatch.setattr(tariff_handler, "insert_tariff", fake_insert)

    response = Response()
    payload = await tariff_handler.create_tariffs(
        RequestStub(
            {
                "code": "pro",
                "name": "Pro",
                "price": "100",
                "isActive": False,
            }
        ),
        response,
        object(),
    )

    assert response.status_code == 409
    assert payload["error"]["code"] == "TARIFF_EXISTS"
    assert insert_called is False


@pytest.mark.asyncio
async def test_invalid_tariff_price_returns_validation_error(monkeypatch):
    async def fake_get_by_code(_session, _code):
        return None

    monkeypatch.setattr(tariff_handler, "get_tariff_by_code", fake_get_by_code)

    response = Response()
    payload = await tariff_handler.create_tariffs(
        RequestStub(
            {
                "code": "pro",
                "name": "Pro",
                "price": "не-число",
                "isActive": False,
            }
        ),
        response,
        object(),
    )

    assert response.status_code == 400
    assert payload["error"]["code"] == "PRICE_INVALID"
    assert payload["error"]["message"] == "Цена тарифа должна быть числом"


def test_tariff_handler_uses_request_transaction_boundary_and_russian_messages():
    source = (
        Path(__file__).resolve().parents[1]
        / "handlers"
        / "control_panel"
        / "tariffs.py"
    ).read_text(encoding="utf-8")

    forbidden = (
        "db_session.commit(",
        "db_session.rollback(",
        "message=str(e)",
        "Tariff not found",
        "Tariff status not changed",
        "Tariff not updated",
        "Tariff not deleted",
        "Tariff limits data is required",
        "Limit not found",
        "Limit not updated",
        "Limit not deleted",
        "DB QUERY",
        "ALL LIMITS",
    )

    for phrase in forbidden:
        assert phrase not in source, (
            f"В тарифном handler снова появился запрещённый контракт: {phrase}"
        )



def test_tariff_service_does_not_swallow_database_errors():
    source = (
        Path(__file__).resolve().parents[1]
        / "services"
        / "tariff_service.py"
    ).read_text(encoding="utf-8")

    forbidden = (
        "except Exception",
        "session.rollback(",
        "Error inserting tariff",
        "Error updating tariff",
        "Error deleting tariff",
        "Error updating limit",
        "Error deleting limit",
        "Hiding incomplete public tariff",
        "Refusing unsafe update",
    )

    for phrase in forbidden:
        assert phrase not in source, (
            f"В tariff_service снова появился запрещённый контракт: {phrase}"
        )
