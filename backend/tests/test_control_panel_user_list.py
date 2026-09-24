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


def test_staff_creation_payload_normalizes_required_fields():
    data = control_panel_users._validated_staff_creation_payload({
        "full_name": "  Иван Петров  ",
        "email": "  STAFF@Example.COM ",
        "phone": " +7 (999) 000-00-01 ",
        "password": "TempPass123!",
        "role": "manager",
        "timezone": "Europe/Moscow",
        "staff_id": " EMP-001 ",
        "department": " Поддержка ",
        "position": " Менеджер ",
    })

    assert data["full_name"] == "Иван Петров"
    assert data["email"] == "staff@example.com"
    assert data["phone"] == "+79990000001"
    assert data["role"] == "manager"
    assert data["staff_id"] == "EMP-001"
    assert data["department"] == "Поддержка"
    assert data["position"] == "Менеджер"


@pytest.mark.parametrize("role", ["user", "super_admin", "root", ""])
def test_staff_creation_rejects_role_outside_safe_admin_list(role):
    with pytest.raises(control_panel_users.StaffCreationError) as exc_info:
        control_panel_users._validated_staff_creation_payload({
            "full_name": "Иван Петров",
            "email": "staff@example.com",
            "phone": "+79990000001",
            "password": "TempPass123!",
            "role": role,
        })

    assert exc_info.value.code == "STAFF_ROLE_INVALID"


def test_control_panel_user_router_exposes_staff_creation_and_delete_flows():
    routes = {
        (route.path, method)
        for route in control_panel_users.router.routes
        for method in route.methods
    }

    assert ("/control-panel/users/", "POST") in routes
    assert ("/control-panel/users/{user_uuid}", "DELETE") in routes
    assert ("/control-panel/users/{user_uuid}/purge", "DELETE") in routes
