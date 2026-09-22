from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi import Response
from sqlalchemy import select

from handlers.control_panel import users as control_panel_users
from models.users_model import User, UserRoleAssociation


def test_escape_like_treats_wildcards_as_literal_search_text():
    assert control_panel_users._escape_like("seller_100%\\") == "seller\\_100\\%\\\\"


def test_user_list_conditions_cover_client_status_and_role_filters():
    conditions = control_panel_users._user_list_conditions(
        search="seller@example.com",
        active=True,
        verified=False,
        staff=False,
        role="user",
    )
    statement = select(User).where(*conditions)
    sql = str(statement)

    assert "users.is_active IS true" in sql
    assert "users.email_verified_at IS NULL" in sql
    assert "users.is_staff IS false" in sql
    assert "user_roles" in sql
    assert "EXISTS" in sql
    assert "lower(users.email)" in sql


@pytest.mark.asyncio
async def test_invalid_user_role_filter_returns_stable_400_without_querying_database():
    class ForbiddenSession:
        async def execute(self, *_args, **_kwargs):
            raise AssertionError("invalid role filter must fail before DB query")

        async def scalar(self, *_args, **_kwargs):
            raise AssertionError("invalid role filter must fail before DB count")

    response = Response()
    result = await control_panel_users.get_users(
        response=response,
        search=None,
        active=None,
        verified=None,
        staff=None,
        role="root",
        limit=50,
        offset=0,
        db_session=ForbiddenSession(),  # type: ignore[arg-type]
    )

    assert response.status_code == 400
    assert result["status"] == "error"
    assert result["error"]["code"] == "USER_FILTER_INVALID"


@pytest.mark.asyncio
async def test_user_list_returns_server_side_total_limit_and_offset():
    user = User(
        id=UUID("22222222-2222-4222-8222-222222222222"),
        email="seller@example.com",
        phone="+79990000000",
        hashed_password="hashed",
        full_name="Seller",
        entity_type="individual",
        timezone="Europe/Moscow",
        created_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
        is_active=True,
        is_staff=False,
        roles=[
            UserRoleAssociation(
                role="user",
                assigned_at=datetime(2026, 9, 20, tzinfo=timezone.utc),
            )
        ],
    )

    class FakeScalars:
        def unique(self):
            return self

        def all(self):
            return [user]

    class FakeResult:
        def scalars(self):
            return FakeScalars()

    class FakeSession:
        def __init__(self):
            self.statement = None
            self.count_statement = None

        async def execute(self, statement):
            self.statement = statement
            return FakeResult()

        async def scalar(self, statement):
            self.count_statement = statement
            return 137

    session = FakeSession()
    response = Response()
    result = await control_panel_users.get_users(
        response=response,
        search="seller",
        active=True,
        verified=None,
        staff=False,
        role="user",
        limit=25,
        offset=50,
        db_session=session,  # type: ignore[arg-type]
    )

    assert result["status"] == "success"
    assert result["total"] == 137
    assert result["limit"] == 25
    assert result["offset"] == 50
    assert len(result["user_list"]) == 1

    sql = str(session.statement)
    assert "LIMIT" in sql
    assert "OFFSET" in sql
    assert "users.is_staff IS false" in sql
