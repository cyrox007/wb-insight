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


def test_expense_mutations_reject_invalid_fields_with_http_400():
    root = Path(__file__).resolve().parents[1]
    source = (root / "handlers" / "dashboard" / "expense_handler.py").read_text(
        encoding="utf-8"
    )
    # Создание и изменение должны назначать статус перед ответом об ошибке.
    assert source.count('response.status_code = status.HTTP_400_BAD_REQUEST') >= 4
    assert source.count('code="INVALID_EXPENSE"') == 2


def test_expense_update_validates_before_mutating_orm():
    root = Path(__file__).resolve().parents[1]
    source = (root / "handlers" / "dashboard" / "expense_handler.py").read_text(
        encoding="utf-8"
    )
    update_source = source.split("async def update_expense(", 1)[1].split(
        "@router.delete", 1
    )[0]
    validation_end = update_source.index('code="INVALID_EXPENSE"')
    mutation_start = update_source.index("for field, value in changes.items():")
    assert validation_end < mutation_start
    assert "setattr(expense, field, value)" in update_source[mutation_start:]
    assert "expense.date =" not in update_source
    assert "expense.amount =" not in update_source
    assert "expense.category =" not in update_source
