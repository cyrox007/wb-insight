from types import SimpleNamespace
from uuid import uuid4

import pytest

from services import sync_onboarding_service, token_services
from services.user_sync_state_service import SYNC_ENTITIES


@pytest.mark.asyncio
async def test_bootstrap_token_sync_creates_states_and_jobs_for_all_entities(
    monkeypatch,
):
    user_id = uuid4()
    token_id = uuid4()
    calls: list[tuple[str, dict]] = []

    async def fake_ensure_states(*, session, user_id: object, token_id: object):
        assert session is fake_session
        assert user_id == expected_user_id
        assert token_id == expected_token_id
        return len(SYNC_ENTITIES)

    def fake_build_payload(entity: str):
        return {"entity": entity}

    async def fake_create_job(
        *,
        session,
        user_id: object,
        token_id: object,
        entity: str,
        payload: dict,
    ):
        assert session is fake_session
        assert user_id == expected_user_id
        assert token_id == expected_token_id
        calls.append((entity, payload))
        return True

    fake_session = object()
    expected_user_id = user_id
    expected_token_id = token_id

    monkeypatch.setattr(
        sync_onboarding_service,
        "ensure_token_sync_states",
        fake_ensure_states,
    )
    monkeypatch.setattr(
        sync_onboarding_service,
        "build_payload_for_entity",
        fake_build_payload,
    )
    monkeypatch.setattr(
        sync_onboarding_service,
        "create_sync_job",
        fake_create_job,
    )

    states_created, jobs_created = await sync_onboarding_service.bootstrap_token_sync(
        fake_session,
        user_id,
        token_id,
    )

    assert states_created == len(SYNC_ENTITIES)
    assert jobs_created == len(SYNC_ENTITIES)
    assert [entity for entity, _payload in calls] == list(SYNC_ENTITIES)
    assert all(payload == {"entity": entity} for entity, payload in calls)


@pytest.mark.asyncio
async def test_bootstrap_token_sync_counts_only_new_jobs(monkeypatch):
    user_id = uuid4()
    token_id = uuid4()
    created_entities = {SYNC_ENTITIES[0], SYNC_ENTITIES[3]}

    async def fake_ensure_states(**_kwargs):
        return 0

    async def fake_create_job(*, entity: str, **_kwargs):
        return entity in created_entities

    monkeypatch.setattr(
        sync_onboarding_service,
        "ensure_token_sync_states",
        fake_ensure_states,
    )
    monkeypatch.setattr(
        sync_onboarding_service,
        "create_sync_job",
        fake_create_job,
    )
    monkeypatch.setattr(
        sync_onboarding_service,
        "build_payload_for_entity",
        lambda entity: {"entity": entity},
    )

    states_created, jobs_created = await sync_onboarding_service.bootstrap_token_sync(
        object(),
        user_id,
        token_id,
    )

    assert states_created == 0
    assert jobs_created == 2


class FailingTokenSession:
    def __init__(self):
        self.added = None

    def add(self, value):
        self.added = value

    async def flush(self):
        raise RuntimeError("ошибка тестовой базы данных")


@pytest.mark.asyncio
async def test_insert_token_does_not_hide_database_failure(monkeypatch):
    user_id = uuid4()
    session = FailingTokenSession()
    metadata = SimpleNamespace(
        token_type="service",
        seller_id="seller-1",
        expires_at=None,
    )

    monkeypatch.setattr(token_services, "decode_wb_token", lambda _token: metadata)
    monkeypatch.setattr(
        token_services,
        "validate_cloud_service_token",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        token_services,
        "validate_analytics_permissions",
        lambda *_args, **_kwargs: None,
    )

    async def fake_live_validation(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        token_services,
        "validate_wb_token_live",
        fake_live_validation,
    )
    monkeypatch.setattr(
        token_services,
        "encrypt_token",
        lambda raw_token, _user_id: f"encrypted:{raw_token}",
    )

    with pytest.raises(RuntimeError, match="ошибка тестовой базы данных"):
        await token_services.insert_token(
            session=session,
            user_id=user_id,
            raw_token="test-token",
        )

    assert session.added is not None
