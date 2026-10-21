from pathlib import Path

import pytest

from utils.request_payload import request_json_object


class _Запрос:
    def __init__(self, payload=None, error: Exception | None = None):
        self.payload = payload
        self.error = error

    async def json(self):
        if self.error is not None:
            raise self.error
        return self.payload


@pytest.mark.asyncio
async def test_request_json_object_accepts_only_object():
    assert await request_json_object(_Запрос({"value": 1})) == {"value": 1}
    assert await request_json_object(_Запрос(["value"])) is None
    assert await request_json_object(_Запрос("value")) is None
    assert await request_json_object(_Запрос(None)) is None


@pytest.mark.asyncio
async def test_request_json_object_handles_invalid_json():
    assert await request_json_object(_Запрос(error=ValueError("битый JSON"))) is None
    assert await request_json_object(_Запрос(error=TypeError("неподдерживаемый тип"))) is None


def test_dashboard_mutation_handlers_use_safe_json_object_contract():
    root = Path(__file__).resolve().parents[1]
    handlers = {
        "biling_handler.py": 2,
        "cost_price_handler.py": 1,
        "expense_handler.py": 2,
        "profile_handler.py": 1,
        "token_handler.py": 1,
    }

    for filename, expected_calls in handlers.items():
        source = (root / "handlers" / "dashboard" / filename).read_text(encoding="utf-8")
        assert source.count("request_json_object(request)") >= expected_calls
        if filename != "profile_handler.py":
            assert "await request.json()" not in source


def test_safe_json_contract_returns_explicit_client_error():
    root = Path(__file__).resolve().parents[1]
    for filename in (
        "biling_handler.py",
        "cost_price_handler.py",
        "expense_handler.py",
        "profile_handler.py",
        "token_handler.py",
    ):
        source = (root / "handlers" / "dashboard" / filename).read_text(encoding="utf-8")
        assert "REQUEST_PAYLOAD_INVALID" in source
        assert "HTTP_400_BAD_REQUEST" in source
