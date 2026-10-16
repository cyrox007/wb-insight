from inspect import signature
from pathlib import Path

import pytest

from handlers.control_panel.operations import list_diagnostic_events
from services.operation_filter_service import (
    parse_http_statuses,
    validate_http_status_group,
)


def test_http_status_filter_parses_multiple_unique_codes():
    assert parse_http_statuses("401, 403,429,401") == (401, 403, 429)
    assert parse_http_statuses("") == ()


def test_http_status_filter_rejects_invalid_values():
    with pytest.raises(ValueError, match="числами через запятую"):
        parse_http_statuses("401,abc")

    with pytest.raises(ValueError, match="диапазоне"):
        parse_http_statuses("999")


def test_http_status_group_contract_is_explicit():
    assert validate_http_status_group("4xx") == "4xx"
    assert validate_http_status_group("errors") == "errors"

    with pytest.raises(ValueError, match="Неизвестная группа"):
        validate_http_status_group("6xx")


def test_diagnostics_events_api_exposes_combined_filter_contract():
    parameters = signature(list_diagnostic_events).parameters
    expected = {
        "user_query",
        "token_query",
        "payment_query",
        "tariff_query",
        "job_query",
        "operation_id",
        "request_id",
        "domain",
        "operation",
        "event_status",
        "severity",
        "component",
        "event_kind",
        "direction",
        "provider",
        "http_statuses",
        "http_status_group",
        "error_code",
        "min_duration_ms",
        "created_from",
        "created_to",
        "attention_only",
        "unfinished_only",
        "retry_only",
        "limit",
        "offset",
    }

    assert expected <= set(parameters)


def test_control_panel_filter_ui_exposes_entity_and_attention_presets():
    root = Path(__file__).resolve().parents[2]
    panel = (
        root
        / "frontend"
        / "src"
        / "pages"
        / "ControlPanel"
        / "Diagnostics"
        / "FilterPanel.vue"
    ).read_text(encoding="utf-8")
    hub = (
        root
        / "frontend"
        / "src"
        / "pages"
        / "ControlPanel"
        / "Diagnostics"
        / "Hub.vue"
    ).read_text(encoding="utf-8")

    assert "Пользователь" in panel
    assert "Токен / кабинет" in panel
    assert "Платёж" in panel
    assert "Тариф" in panel
    assert "Задача синхронизации" in panel
    assert "Требует внимания" in panel
    assert "401 / 403" in panel
    assert "Незавершённые" in panel
    assert "Повторные попытки" in panel
    assert "Показать журнал" in hub
    assert "Отфильтрованный журнал" in hub
