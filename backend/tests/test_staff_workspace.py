from datetime import datetime, timezone

import pytest

from core.access_control import Permission
from handlers.control_panel import home


@pytest.mark.asyncio
async def test_support_attention_exposes_only_user_aggregates(monkeypatch):
    async def unexpected_count(*_args, **_kwargs):
        raise AssertionError("support role must not query mail/payment aggregates")

    monkeypatch.setattr(home, "_count", unexpected_count)

    result = await home._attention_summary(
        object(),  # type: ignore[arg-type]
        permissions={
            Permission.CONTROL_PANEL_ACCESS.value,
            Permission.USERS_READ.value,
            Permission.AUDIT_READ.value,
        },
        account_health={"unverified": 7, "inactive": 2},
        now=datetime(2026, 9, 21, 18, 0, tzinfo=timezone.utc),
    )

    assert result == {
        "users": {
            "unverified": 7,
            "inactive": 2,
        }
    }


@pytest.mark.asyncio
async def test_manager_attention_is_permission_scoped_and_aggregate(monkeypatch):
    values = iter([3, 1, 4, 2])

    async def fake_count(*_args, **_kwargs):
        return next(values)

    monkeypatch.setattr(home, "_count", fake_count)

    result = await home._attention_summary(
        object(),  # type: ignore[arg-type]
        permissions={
            Permission.CONTROL_PANEL_ACCESS.value,
            Permission.USERS_READ.value,
            Permission.MAIL_READ.value,
            Permission.PAYMENTS_READ.value,
        },
        account_health={"unverified": 5, "inactive": 1},
        now=datetime(2026, 9, 21, 18, 0, tzinfo=timezone.utc),
    )

    assert result["users"] == {"unverified": 5, "inactive": 1}
    assert result["mail"]["failed_recent"] == 3
    assert result["mail"]["stale_queued"] == 1
    assert result["payments"] == {
        "failed_24h": 4,
        "pending_over_24h": 2,
    }
    assert "system" not in result


@pytest.mark.asyncio
async def test_analyst_attention_does_not_disclose_restricted_aggregates(monkeypatch):
    async def unexpected_count(*_args, **_kwargs):
        raise AssertionError("analyst role must not query restricted aggregates")

    monkeypatch.setattr(home, "_count", unexpected_count)

    result = await home._attention_summary(
        object(),  # type: ignore[arg-type]
        permissions={Permission.CONTROL_PANEL_ACCESS.value},
        account_health={"unverified": 99, "inactive": 88},
        now=datetime(2026, 9, 21, 18, 0, tzinfo=timezone.utc),
    )

    assert result == {}


@pytest.mark.asyncio
async def test_super_admin_attention_includes_system_health(monkeypatch):
    values = iter([0, 0, 0, 0])

    async def fake_count(*_args, **_kwargs):
        return next(values)

    async def fake_snapshot(*_args, **_kwargs):
        return {
            "status": "warning",
            "checks": {
                "mail_queue_stale": {"status": "warning"},
                "http_5xx": {"status": "ok"},
                "wb_service_secret": {"status": "not_applicable"},
            },
        }

    monkeypatch.setattr(home, "_count", fake_count)
    monkeypatch.setattr(home, "build_operational_snapshot", fake_snapshot)

    result = await home._attention_summary(
        object(),  # type: ignore[arg-type]
        permissions={
            Permission.CONTROL_PANEL_ACCESS.value,
            Permission.USERS_READ.value,
            Permission.MAIL_READ.value,
            Permission.PAYMENTS_READ.value,
            Permission.SYSTEM_MANAGE.value,
        },
        account_health={"unverified": 0, "inactive": 0},
        now=datetime(2026, 9, 21, 18, 0, tzinfo=timezone.utc),
    )

    assert result["system"] == {
        "status": "warning",
        "issue_count": 1,
    }
