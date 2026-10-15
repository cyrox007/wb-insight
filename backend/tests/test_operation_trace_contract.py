import hashlib
import json
from pathlib import Path
from uuid import uuid4

from core.operation_context import (
    OperationContext,
    bind_actor_user,
    bind_operation_context,
    get_actor_user_id,
    next_operation_sequence,
    reset_operation_context,
)
from core.operation_trace import _decode_body


def test_operation_context_keeps_actor_and_step_sequence():
    operation_id = uuid4()
    user_id = uuid4()
    token = bind_operation_context(
        OperationContext(operation_id=operation_id, request_id="request-12345678")
    )
    try:
        assert next_operation_sequence() == 1
        bind_actor_user(user_id)
        assert get_actor_user_id() == user_id
        assert next_operation_sequence() == 2
        assert next_operation_sequence() == 3
    finally:
        reset_operation_context(token)


def test_http_json_capture_masks_secrets_and_keeps_safe_identifiers():
    body = json.dumps(
        {
            "email": "seller@example.ru",
            "password": "secret-password",
            "token": "raw-wb-token",
            "token_id": "safe-token-id",
            "nested": {"authorization": "Bearer secret", "order_id": "order-1"},
        }
    ).encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()

    payload = _decode_body(
        body,
        total_bytes=len(body),
        digest=digest,
        content_type="application/json",
    )

    assert payload["sha256"] == digest
    assert payload["truncated"] is False
    assert payload["data"]["password"] == "[СКРЫТО]"
    assert payload["data"]["token"] == "[СКРЫТО]"
    assert payload["data"]["nested"]["authorization"] == "[СКРЫТО]"
    assert payload["data"]["token_id"] == "safe-token-id"
    assert payload["data"]["nested"]["order_id"] == "order-1"


def test_truncated_json_is_not_parsed_as_partial_business_payload():
    captured = b'{"items": [1, 2'
    payload = _decode_body(
        captured,
        total_bytes=len(captured) + 100,
        digest="0" * 64,
        content_type="application/json",
    )

    assert payload["truncated"] is True
    assert payload["data"] == "[JSON ОБРЕЗАН; ПОЛНОЕ ТЕЛО ИДЕНТИФИЦИРУЕТСЯ ПО SHA256]"


def test_trace_contract_covers_http_database_background_and_external_steps():
    root = Path(__file__).resolve().parents[1]
    operation_trace = (root / "core" / "operation_trace.py").read_text(encoding="utf-8")
    dependencies = (root / "core" / "dependencies.py").read_text(encoding="utf-8")
    sync_worker = (root / "tasks" / "processors" / "job_processor.py").read_text(encoding="utf-8")
    mail_worker = (root / "tasks" / "processors" / "mail_delivery.py").read_text(encoding="utf-8")
    wb_client = (root / "integrations" / "wildberries" / "client.py").read_text(encoding="utf-8")
    sber_client = (root / "integrations" / "sber" / "client.py").read_text(encoding="utf-8")

    assert "request_received" in operation_trace
    assert "request_completed" in operation_trace
    assert "commit_started" in dependencies
    assert "transaction_rolled_back" in dependencies
    assert "OperationContext" in sync_worker
    assert "OperationContext" in mail_worker
    assert "trace_external_request" in wb_client
    assert "trace_external_response" in wb_client
    assert "trace_external_request" in sber_client
    assert "trace_external_response" in sber_client


def test_diagnostic_explorer_supports_all_correlation_identifiers():
    root = Path(__file__).resolve().parents[2]
    hub = (
        root / "frontend" / "src" / "pages" / "ControlPanel" / "Diagnostics" / "Hub.vue"
    ).read_text(encoding="utf-8")
    api = (
        root / "frontend" / "src" / "API" / "ControlPanel" / "CP_Diagnostics.js"
    ).read_text(encoding="utf-8")

    for identifier in (
        "operation_id",
        "request_id",
        "token_id",
        "payment_id",
        "tariff_id",
        "job_id",
    ):
        assert identifier in hub
    assert "/diagnostics/search" in api
    assert "/diagnostics/operations/" in api
    assert "/diagnostics/requests/" in api
