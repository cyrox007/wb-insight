from pathlib import Path

from core.access_control import Permission, has_permission
from models.users_model import UserRole
from services.operation_log_service import sanitize_operation_data
from tasks.processors import job_processor
from integrations.wildberries.client import (
    WBAuthError,
    WBFeatureUnavailableError,
    WBPermissionError,
    WBRateLimitError,
)


def test_operation_sanitizer_hides_secrets_but_preserves_identifiers():
    payload = sanitize_operation_data(
        {
            "token": "raw-wb-token",
            "token_id": "safe-id",
            "api_key": "secret-key",
            "authorization": "Bearer raw",
            "card_number": "4111111111111111",
            "cvv": "123",
            "formUrl": "https://bank.example/pay?secret=1",
            "payment_id": "pay-id",
            "nested": {"refresh_token": "secret", "order_id": "order-1"},
        }
    )

    assert payload["token"] == "[СКРЫТО]"
    assert payload["api_key"] == "[СКРЫТО]"
    assert payload["authorization"] == "[СКРЫТО]"
    assert payload["card_number"] == "[СКРЫТО]"
    assert payload["cvv"] == "[СКРЫТО]"
    assert payload["formUrl"] == "[СКРЫТО]"
    assert payload["nested"]["refresh_token"] == "[СКРЫТО]"
    assert payload["token_id"] == "safe-id"
    assert payload["payment_id"] == "pay-id"
    assert payload["nested"]["order_id"] == "order-1"


def test_diagnostics_permission_is_support_capability_not_client_capability():
    assert has_permission([UserRole.SUPER_ADMIN], Permission.DIAGNOSTICS_READ)
    assert has_permission([UserRole.ADMIN], Permission.DIAGNOSTICS_READ)
    assert has_permission([UserRole.MANAGER], Permission.DIAGNOSTICS_READ)
    assert has_permission([UserRole.SUPPORT], Permission.DIAGNOSTICS_READ)
    assert not has_permission([UserRole.ANALYST], Permission.DIAGNOSTICS_READ)
    assert not has_permission([UserRole.USER], Permission.DIAGNOSTICS_READ)


def test_wb_failures_have_stable_diagnostic_codes():
    assert job_processor._failure_code(
        WBPermissionError("нет прав", endpoint="prices", status_code=403)
    ) == "WB_PERMISSION_DENIED"
    assert job_processor._failure_code(
        WBFeatureUnavailableError("недоступно", endpoint="storage", status_code=402)
    ) == "WB_FEATURE_UNAVAILABLE"
    assert job_processor._failure_code(
        WBAuthError("авторизация", endpoint="orders", status_code=401)
    ) == "WB_AUTH_FAILED"
    assert job_processor._failure_code(
        WBRateLimitError("лимит", endpoint="sales", status_code=429)
    ) == "WB_RATE_LIMITED"


def test_operation_log_migration_is_append_only_and_extends_current_head():
    root = Path(__file__).resolve().parents[1]
    migration = (
        root / "alembic" / "versions" / "b8e1c4d7f260_operation_diagnostics.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision: Union[str, Sequence[str], None] = "a6d4f8c2e951"' in migration
    assert "trg_operation_log_events_append_only" in migration
    assert "BEFORE UPDATE OR DELETE" in migration


def test_diagnostic_page_exposes_calculation_and_correlation_sections():
    root = Path(__file__).resolve().parents[2]
    page = (
        root / "frontend" / "src" / "pages" / "ControlPanel" / "Diagnostics" / "index.vue"
    ).read_text(encoding="utf-8")

    assert "Операционный журнал" in page
    assert "ID операции" in page
    assert "Платёжные операции" in page
    assert "Расчёт дашборда" in page
