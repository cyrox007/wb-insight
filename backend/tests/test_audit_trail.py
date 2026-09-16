from core.audit import (
    audit_result_for_status,
    classify_audit_action,
    infer_audit_target,
    should_audit_request,
)
from services.audit_service import sanitize_audit_metadata


def test_audit_redacts_secret_like_metadata_recursively():
    payload = sanitize_audit_metadata(
        {
            "provider": "sber",
            "password": "do-not-store",
            "nested": {
                "Authorization": "Bearer secret",
                "safe": "visible",
                "api_key": "hidden",
            },
        }
    )
    assert payload["provider"] == "sber"
    assert payload["password"] == "[REDACTED]"
    assert payload["nested"]["Authorization"] == "[REDACTED]"
    assert payload["nested"]["api_key"] == "[REDACTED]"
    assert payload["nested"]["safe"] == "visible"


def test_audit_covers_all_mutations_but_not_normal_dashboard_reads():
    assert should_audit_request("POST", "/dashboard/expenses") is True
    assert should_audit_request("DELETE", "/dashboard/tokens/abc") is True
    assert should_audit_request("GET", "/control-panel/users") is True
    assert should_audit_request("GET", "/dashboard") is False
    assert should_audit_request("GET", "/health/ready") is False


def test_audit_action_classification_is_semantic_for_critical_admin_flows():
    assert classify_audit_action(
        "PUT",
        "/control-panel/payments/providers/{provider}/{mode}",
        "/control-panel/payments/providers/sber/live",
    ) == "admin.payment_provider.update"
    assert classify_audit_action(
        "POST",
        "/control-panel/roles/{user_id}/{role_code}",
        "/control-panel/roles/u/admin",
    ) == "admin.role.assign"
    assert classify_audit_action(
        "POST",
        "/auth/login",
        "/auth/login",
    ) == "auth.login"


def test_audit_target_uses_route_parameters_without_request_body():
    assert infer_audit_target(
        "/control-panel/payments/providers/{provider}/{mode}",
        {"provider": "sber", "mode": "test"},
    ) == ("payment_provider", "sber:test")
    assert infer_audit_target(
        "/control-panel/users/{user_id}",
        {"user_id": "11111111-1111-1111-1111-111111111111"},
    ) == ("user", "11111111-1111-1111-1111-111111111111")


def test_audit_result_distinguishes_denied_from_failed():
    assert audit_result_for_status(204) == "success"
    assert audit_result_for_status(401) == "denied"
    assert audit_result_for_status(403) == "denied"
    assert audit_result_for_status(422) == "failed"
    assert audit_result_for_status(500) == "failed"
