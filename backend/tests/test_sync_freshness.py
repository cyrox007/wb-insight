from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Response

from handlers.dashboard import main_handler, profile_handler
from models.tokens_model import Marketplace
from services.dashboard.account_scope import DashboardAccountScope
from services.user_sync_state_service import SYNC_ENTITIES, build_sync_status


def _state(
    token_id,
    entity,
    *,
    last_success_at=None,
    last_sync_at=None,
    last_error=None,
):
    return SimpleNamespace(
        token_id=token_id,
        entity=entity,
        last_success_at=last_success_at,
        last_sync_at=last_sync_at,
        last_error=last_error,
    )


def test_sync_status_reports_complete_single_account():
    token_id = uuid4()
    now = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
    states = [
        _state(
            token_id,
            entity,
            last_success_at=now + timedelta(minutes=index),
            last_sync_at=now + timedelta(minutes=index),
        )
        for index, entity in enumerate(SYNC_ENTITIES)
    ]

    result = build_sync_status(
        states,
        (token_id,),
        freshness_interval_hours=1,
        now=now + timedelta(minutes=len(SYNC_ENTITIES)),
    )

    assert result["complete"] is True
    assert result["ready_entities"] == len(SYNC_ENTITIES)
    assert result["stale_entities"] == 0
    assert result["error_entities"] == 0
    assert result["waiting_entities"] == 0
    assert result["freshness_policy_available"] is True
    assert result["freshness_interval_hours"] == 1
    assert result["oldest_success_at"] == now
    assert result["latest_success_at"] == now + timedelta(
        minutes=len(SYNC_ENTITIES) - 1
    )


def test_sync_status_fails_safe_for_multi_account_partial_freshness():
    first_token = uuid4()
    second_token = uuid4()
    now = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)

    states = []
    for entity in SYNC_ENTITIES:
        states.append(
            _state(
                first_token,
                entity,
                last_success_at=now,
                last_sync_at=now,
            )
        )
        if entity == "orders":
            states.append(
                _state(
                    second_token,
                    entity,
                    last_success_at=now - timedelta(hours=2),
                    last_sync_at=now,
                    last_error="внутренняя ошибка не должна попасть в API",
                )
            )
        elif entity != "advertising":
            states.append(
                _state(
                    second_token,
                    entity,
                    last_success_at=now - timedelta(minutes=30),
                    last_sync_at=now,
                )
            )

    result = build_sync_status(
        states,
        (first_token, second_token),
        is_syncing=True,
        freshness_interval_hours=1,
        now=now,
    )

    entity_map = {item["entity"]: item for item in result["entities"]}
    assert result["complete"] is False
    assert result["is_syncing"] is True
    assert entity_map["orders"]["status"] == "stale"
    assert entity_map["orders"]["error_accounts"] == 1
    assert entity_map["advertising"]["status"] == "stale"
    assert entity_map["advertising"]["successful_accounts"] == 1
    assert "last_error" not in entity_map["orders"]


def test_sync_status_marks_historical_success_as_stale_after_tariff_interval():
    token_id = uuid4()
    now = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
    states = [
        _state(
            token_id,
            entity,
            last_success_at=now - timedelta(hours=3),
            last_sync_at=now - timedelta(hours=3),
        )
        for entity in SYNC_ENTITIES
    ]

    result = build_sync_status(
        states,
        (token_id,),
        freshness_interval_hours=2,
        now=now,
    )

    assert result["complete"] is False
    assert result["ready_entities"] == 0
    assert result["stale_entities"] == len(SYNC_ENTITIES)
    assert result["freshness_cutoff"] == now - timedelta(hours=2)
    assert all(
        item["fresh_accounts"] == 0 and item["stale_accounts"] == 1
        for item in result["entities"]
    )


class FakeRequest:
    def __init__(self, user_id, payload=None):
        self.state = SimpleNamespace(user={"sub": str(user_id)})
        self.client = SimpleNamespace(host="127.0.0.1")
        self.headers = {"user-agent": "pytest"}
        self._payload = payload or {}

    async def json(self):
        return self._payload


@pytest.mark.asyncio
async def test_dashboard_reports_primary_sync_instead_of_not_synced(monkeypatch):
    user_id = uuid4()
    token_id = uuid4()
    scope = DashboardAccountScope(
        token_ids=(token_id,),
        selected_token_id=token_id,
    )
    states = [
        _state(token_id, entity)
        for entity in SYNC_ENTITIES
    ]

    async def fake_scope(_session, _user_id, _token_id):
        return scope, None

    async def fake_states(*, session, user_id):
        return states

    async def fake_active_jobs(_session, _user_id, _scope):
        return True

    async def fake_frequency(_session, _user_id):
        return 1

    monkeypatch.setattr(main_handler, "_resolve_scope_or_error", fake_scope)
    monkeypatch.setattr(main_handler, "get_user_sync_states", fake_states)
    monkeypatch.setattr(main_handler, "has_active_sync_jobs", fake_active_jobs)
    monkeypatch.setattr(main_handler, "get_wb_sync_frequency_hours", fake_frequency)

    result = await main_handler.dashboard(
        FakeRequest(user_id),
        db_session=object(),
        token_id=token_id,
    )

    assert result["status"] == "success"
    assert result["is_syncing"] is True
    assert result["is_synced"] is False
    assert result["initial_sync"] is True
    assert result["message"] == "Выполняется первичная синхронизация данных"
    assert result["sync_status"]["waiting_entities"] == len(SYNC_ENTITIES)
    assert result["sync_status"]["is_syncing"] is True


@pytest.mark.asyncio
async def test_legacy_wb_connection_route_bootstraps_primary_sync(monkeypatch):
    user_id = uuid4()
    token_id = uuid4()
    now = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
    token = SimpleNamespace(
        id=token_id,
        user_id=user_id,
        label="Основной кабинет",
        marketplace=Marketplace.WILDBERRIES,
        token_type="service",
        external_account_id="seller-1",
        issued_at=now,
        expires_at=now + timedelta(days=30),
        is_active=True,
        is_revoked=False,
        is_valid=True,
    )
    bootstrap_calls = []

    async def fake_quota(_session, _user_id):
        return {"allowed": True, "code": None, "limit": 1, "used": 0}

    async def fake_insert_token(**_kwargs):
        return token

    async def fake_record_consents(*_args, **_kwargs):
        return None

    async def fake_bootstrap(**kwargs):
        bootstrap_calls.append(kwargs)
        return len(SYNC_ENTITIES), len(SYNC_ENTITIES)

    monkeypatch.setattr(profile_handler, "get_wb_account_quota", fake_quota)
    monkeypatch.setattr(
        profile_handler,
        "validate_consent_payload",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(profile_handler, "insert_token", fake_insert_token)
    monkeypatch.setattr(profile_handler, "record_consents", fake_record_consents)
    monkeypatch.setattr(profile_handler, "bootstrap_token_sync", fake_bootstrap)

    result = await profile_handler.add_token(
        FakeRequest(
            user_id,
            {
                "token": "test-token",
                "label": "Основной кабинет",
                "legal_consents": [],
            },
        ),
        Response(),
        db_session=object(),
    )

    assert result["status"] == "success"
    assert result["sync"] == {
        "states_created": len(SYNC_ENTITIES),
        "jobs_created": len(SYNC_ENTITIES),
    }
    assert len(bootstrap_calls) == 1
    assert bootstrap_calls[0]["user_id"] == user_id
    assert bootstrap_calls[0]["token_id"] == token_id



@pytest.mark.asyncio
async def test_dashboard_keeps_saved_metrics_visible_during_background_sync(monkeypatch):
    user_id = uuid4()
    token_id = uuid4()
    now = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
    scope = DashboardAccountScope(
        token_ids=(token_id,),
        selected_token_id=token_id,
    )
    states = [
        _state(
            token_id,
            entity,
            last_success_at=now,
            last_sync_at=now,
        )
        for entity in SYNC_ENTITIES
    ]

    async def fake_scope(_session, _user_id, _token_id):
        return scope, None

    async def fake_states(*, session, user_id):
        return states

    async def fake_active_jobs(_session, _user_id, _scope):
        return True

    async def fake_frequency(_session, _user_id):
        return 24

    async def fake_stats(*_args, **_kwargs):
        return {
            "stats": {
                "revenue": {"value": 125000.0},
                "profit": {"value": 31000.0},
            },
            "base_stats": {"revenue": 125000.0},
        }

    monkeypatch.setattr(main_handler, "_resolve_scope_or_error", fake_scope)
    monkeypatch.setattr(main_handler, "get_user_sync_states", fake_states)
    monkeypatch.setattr(main_handler, "has_active_sync_jobs", fake_active_jobs)
    monkeypatch.setattr(main_handler, "get_wb_sync_frequency_hours", fake_frequency)
    monkeypatch.setattr(main_handler, "_calculate_stats", fake_stats)

    result = await main_handler.dashboard(
        FakeRequest(user_id),
        db_session=object(),
        token_id=token_id,
    )

    assert result["status"] == "success"
    assert result["is_synced"] is True
    assert result["is_syncing"] is True
    assert result["initial_sync"] is False
    assert result["stats"]["revenue"]["value"] == 125000.0
    assert result["stats"]["profit"]["value"] == 31000.0
    assert "Показаны уже сохранённые значения" in result["message"]


@pytest.mark.asyncio
async def test_sync_status_endpoint_returns_lightweight_scoped_summary(monkeypatch):
    user_id = uuid4()
    token_id = uuid4()
    now = datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)
    scope = DashboardAccountScope(
        token_ids=(token_id,),
        selected_token_id=token_id,
    )
    states = [
        _state(
            token_id,
            entity,
            last_success_at=now,
            last_sync_at=now,
        )
        for entity in SYNC_ENTITIES
    ]

    async def fake_scope(_session, _user_id, _token_id):
        return scope, None

    async def fake_states(*, session, user_id):
        return states

    async def fake_active_jobs(_session, _user_id, _scope):
        return False

    async def fake_frequency(_session, _user_id):
        return 24

    monkeypatch.setattr(main_handler, "_resolve_scope_or_error", fake_scope)
    monkeypatch.setattr(main_handler, "get_user_sync_states", fake_states)
    monkeypatch.setattr(main_handler, "has_active_sync_jobs", fake_active_jobs)
    monkeypatch.setattr(main_handler, "get_wb_sync_frequency_hours", fake_frequency)

    result = await main_handler.dashboard_sync_status(
        FakeRequest(user_id),
        db_session=object(),
        token_id=token_id,
    )

    assert result["status"] == "success"
    assert result["selected_token_id"] == str(token_id)
    assert result["sync_status"]["complete"] is True
    assert result["sync_status"]["ready_entities"] == len(SYNC_ENTITIES)
    assert result["sync_status"]["is_syncing"] is False
