from datetime import datetime, timedelta, timezone

import pytest

from core import http_metrics
from core.ops_config import ops_config
from services import operational_monitoring_service as monitoring
from settings import config


def test_operational_summary_prioritizes_critical_and_warning():
    assert monitoring.summarize_operational_status({"a": {"status": "ok"}}) == "ok"
    assert (
        monitoring.summarize_operational_status(
            {"a": {"status": "ok"}, "b": {"status": "warning"}}
        )
        == "warning"
    )
    assert (
        monitoring.summarize_operational_status(
            {"a": {"status": "warning"}, "b": {"status": "critical"}}
        )
        == "degraded"
    )


def test_wb_service_secret_check_is_not_applicable_without_service_secret(monkeypatch):
    monkeypatch.setattr(config, "WB_SERVICE_SECRET", None)
    result = monitoring._wb_service_secret_check(
        datetime(2026, 9, 15, tzinfo=timezone.utc),
        14,
    )
    assert result == {"status": "not_applicable", "configured": False}


def test_wb_service_secret_check_warns_when_expiry_metadata_is_missing(monkeypatch):
    monkeypatch.setattr(config, "WB_SERVICE_SECRET", "encrypted-outside-this-check")
    monkeypatch.setattr(ops_config, "WB_SERVICE_SECRET_EXPIRES_AT", None)
    result = monitoring._wb_service_secret_check(
        datetime(2026, 9, 15, tzinfo=timezone.utc),
        14,
    )
    assert result["status"] == "warning"
    assert result["reason"] == "expiry_not_configured"
    assert "secret" not in result


def test_wb_service_secret_check_rejects_invalid_or_naive_expiry(monkeypatch):
    monkeypatch.setattr(config, "WB_SERVICE_SECRET", "secret")

    monkeypatch.setattr(ops_config, "WB_SERVICE_SECRET_EXPIRES_AT", "not-a-date")
    assert monitoring._wb_service_secret_check(
        datetime(2026, 9, 15, tzinfo=timezone.utc), 14
    )["status"] == "critical"

    monkeypatch.setattr(ops_config, "WB_SERVICE_SECRET_EXPIRES_AT", "2026-10-01T12:00:00")
    assert monitoring._wb_service_secret_check(
        datetime(2026, 9, 15, tzinfo=timezone.utc), 14
    )["status"] == "critical"


def test_wb_service_secret_check_tracks_rotation_window(monkeypatch):
    current = datetime(2026, 9, 15, tzinfo=timezone.utc)
    monkeypatch.setattr(config, "WB_SERVICE_SECRET", "secret")

    monkeypatch.setattr(
        ops_config,
        "WB_SERVICE_SECRET_EXPIRES_AT",
        (current + timedelta(days=7)).isoformat(),
    )
    warning = monitoring._wb_service_secret_check(current, 14)
    assert warning["status"] == "warning"
    assert warning["days_remaining"] == 7

    monkeypatch.setattr(
        ops_config,
        "WB_SERVICE_SECRET_EXPIRES_AT",
        (current + timedelta(days=30)).isoformat(),
    )
    healthy = monitoring._wb_service_secret_check(current, 14)
    assert healthy["status"] == "ok"

    monkeypatch.setattr(
        ops_config,
        "WB_SERVICE_SECRET_EXPIRES_AT",
        (current - timedelta(seconds=1)).isoformat(),
    )
    expired = monitoring._wb_service_secret_check(current, 14)
    assert expired["status"] == "critical"


@pytest.mark.asyncio
async def test_http_metrics_are_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(ops_config, "HTTP_METRICS_ENABLED", False)
    assert await http_metrics.read_http_counters(5) == (0, 0)
    await http_metrics.record_http_status(500)


def test_operations_route_is_registered():
    from app import app

    assert "/control-panel/operations/health" in app.openapi()["paths"]
