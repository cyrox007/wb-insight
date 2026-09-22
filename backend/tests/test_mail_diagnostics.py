from types import SimpleNamespace
from uuid import UUID

import pytest

from handlers.control_panel import mail as control_panel_mail


@pytest.mark.asyncio
async def test_password_reset_diagnostics_returns_only_safe_aggregate(monkeypatch):
    captured = {}

    class FakeSession:
        async def scalar(self, statement):
            captured["statement"] = str(statement)
            return 1

    monkeypatch.setattr(
        control_panel_mail.lifecycle_config,
        "PASSWORD_RESET_RESEND_SECONDS",
        90,
    )

    result = await control_panel_mail.password_reset_diagnostics(
        UUID("22222222-2222-4222-8222-222222222222"),
        FakeSession(),  # type: ignore[arg-type]
    )

    assert result["status"] == "success"
    assert result["password_reset_messages"] == 1
    assert result["resend_seconds"] == 90
    assert "recipient_email" not in result
    assert "provider_message_id" not in result
    assert "token" not in result
    assert "mail_messages.user_id" in captured["statement"]
    assert "mail_messages.template_code" in captured["statement"]


@pytest.mark.asyncio
async def test_password_reset_diagnostics_normalizes_empty_count(monkeypatch):
    class FakeSession:
        async def scalar(self, _statement):
            return None

    monkeypatch.setattr(
        control_panel_mail.lifecycle_config,
        "PASSWORD_RESET_RESEND_SECONDS",
        60,
    )

    result = await control_panel_mail.password_reset_diagnostics(
        UUID("33333333-3333-4333-8333-333333333333"),
        FakeSession(),  # type: ignore[arg-type]
    )

    assert result["password_reset_messages"] == 0
    assert result["resend_seconds"] == 60
