from fastapi import Response, status
import pytest

from handlers import health_handler


@pytest.mark.asyncio
async def test_liveness_does_not_depend_on_external_services():
    assert await health_handler.liveness() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_is_ok_when_database_and_redis_are_available(monkeypatch):
    async def database_ok():
        return True

    async def redis_ok():
        return True

    monkeypatch.setattr(health_handler.Database, "health_check", database_ok)
    monkeypatch.setattr(health_handler, "_redis_health_check", redis_ok)

    response = Response()
    payload = await health_handler.readiness(response)

    assert response.status_code == status.HTTP_200_OK
    assert payload == {
        "status": "ok",
        "checks": {"database": "ok", "redis": "ok"},
    }


@pytest.mark.asyncio
async def test_readiness_returns_503_when_dependency_is_unavailable(monkeypatch):
    async def database_ok():
        return True

    async def redis_down():
        return False

    monkeypatch.setattr(health_handler.Database, "health_check", database_ok)
    monkeypatch.setattr(health_handler, "_redis_health_check", redis_down)

    response = Response()
    payload = await health_handler.readiness(response)

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert payload == {
        "status": "degraded",
        "checks": {"database": "ok", "redis": "error"},
    }
