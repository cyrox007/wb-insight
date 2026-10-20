from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from services.incident_triage_service import (
    _deduplicate,
    _diagnostic_query,
    _event_code,
    _event_severity,
    _fingerprint,
)


def test_incident_event_classification_prefers_explicit_error_code():
    event = SimpleNamespace(
        severity="info",
        http_status=503,
        status="failed",
        error_code="WB_API_ERROR",
    )

    assert _event_code(event) == "WB_API_ERROR"
    assert _event_severity(event) == "critical"


def test_incident_diagnostics_prefers_exact_operation_chain():
    operation_id = uuid4()
    user_id = uuid4()

    query = _diagnostic_query(
        user_id=user_id,
        operation_id=operation_id,
        request_id="request-123",
    )

    assert query == {"operation_id": str(operation_id)}


def test_incident_fingerprint_is_stable_and_deduplication_counts_occurrences():
    incident_id = _fingerprint("sync_job", "SYNC_JOB_FAILED", "sync", "user", "sync_job", "job")
    base = {
        "id": incident_id,
        "severity": "error",
        "first_seen_at": "2026-10-20T08:00:00+00:00",
        "last_seen_at": "2026-10-20T08:01:00+00:00",
        "occurrences": 2,
        "title": "Первая ошибка",
    }
    newer = {
        **base,
        "last_seen_at": "2026-10-20T08:05:00+00:00",
        "occurrences": 3,
        "title": "Последняя ошибка",
    }

    items = _deduplicate([base, newer])

    assert len(items) == 1
    assert items[0]["occurrences"] == 5
    assert items[0]["first_seen_at"] == "2026-10-20T08:00:00+00:00"
    assert items[0]["last_seen_at"] == "2026-10-20T08:05:00+00:00"
    assert items[0]["title"] == "Последняя ошибка"


def test_incident_center_frontend_and_api_contract_are_connected():
    root = Path(__file__).resolve().parents[2]
    api = (
        root
        / "frontend"
        / "src"
        / "API"
        / "ControlPanel"
        / "CP_Diagnostics.js"
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
    center = (
        root
        / "frontend"
        / "src"
        / "pages"
        / "ControlPanel"
        / "Diagnostics"
        / "IncidentCenter.vue"
    ).read_text(encoding="utf-8")

    assert "/control-panel/operations/diagnostics/incidents" in api
    assert "IncidentCenter" in hub
    assert "Открыть в диагностике" in center
    assert "Очередь операционных инцидентов" in center
