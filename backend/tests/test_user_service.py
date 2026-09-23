from pathlib import Path

import pytest

from models.users_model import User
from services.user_service import (
    create_user_role_association,
    delete_role_association,
    delete_user,
    get_role_associations_for_update,
    get_user_by_email,
    get_user_by_inn,
    insert_user,
    update_user,
)


class FakeSession:
    def __init__(self):
        self.added = None
        self.flush_count = 0
        self.refresh_count = 0

    def add(self, obj):
        self.added = obj

    async def flush(self):
        self.flush_count += 1

    async def refresh(self, _obj):
        self.refresh_count += 1


@pytest.mark.asyncio
async def test_insert_user_flushes_before_refresh_and_accepts_optional_legal_fields():
    session = FakeSession()
    user = await insert_user(
        session,
        {
            "email": "user@example.com",
            "phone": "+10000000000",
            "full_name": "Test User",
            "password": "a-secure-test-password",
            "entity_type": "individual",
        },
    )

    assert user is not None
    assert session.added is user
    assert session.flush_count == 1
    assert session.refresh_count == 1
    assert user.email == "user@example.com"
    assert user.inn is None
    assert user.kpp is None
    assert user.legal_address is None


@pytest.mark.asyncio
async def test_insert_user_normalizes_email_to_lowercase():
    session = FakeSession()
    user = await insert_user(
        session,
        {
            "email": "  User.Name@Example.COM  ",
            "phone": "+10000000009",
            "full_name": "Пользователь",
            "password": "a-secure-test-password",
            "entity_type": "individual",
        },
    )

    assert user.email == "user.name@example.com"


@pytest.mark.asyncio
async def test_insert_user_normalizes_inn_whitespace():
    session = FakeSession()
    user = await insert_user(
        session,
        {
            "email": "inn@example.com",
            "phone": "+10000000010",
            "full_name": "Пользователь",
            "password": "a-secure-test-password",
            "entity_type": "legal_entity",
            "inn": " 7707083893 ",
        },
    )

    assert user.inn == "7707083893"


@pytest.mark.asyncio
async def test_get_user_by_email_uses_case_insensitive_lookup():
    captured = {}

    class Result:
        def scalar_one_or_none(self):
            return None

    class Session:
        async def execute(self, statement):
            captured["statement"] = statement
            captured["params"] = statement.compile().params
            return Result()

    result = await get_user_by_email(Session(), "  User.Name@Example.COM  ")

    assert result is None
    sql = str(captured["statement"]).lower()
    assert "lower(users.email)" in sql
    assert "user.name@example.com" in set(captured["params"].values())


def test_user_model_has_case_insensitive_unique_email_index():
    index = next(
        item
        for item in User.__table__.indexes
        if item.name == "uq_users_email_lower"
    )

    assert index.unique is True
    assert "lower" in str(index.expressions[0]).lower()


@pytest.mark.asyncio
async def test_get_user_by_inn_uses_trimmed_lookup():
    captured = {}

    class Result:
        def scalar_one_or_none(self):
            return None

    class Session:
        async def execute(self, statement):
            captured["statement"] = statement
            captured["params"] = statement.compile().params
            return Result()

    result = await get_user_by_inn(Session(), " 7707083893 ")

    assert result is None
    sql = str(captured["statement"]).lower()
    assert "trim(users.inn)" in sql
    assert "7707083893" in set(captured["params"].values())


def test_user_model_has_unique_normalized_inn_index():
    index = next(
        item
        for item in User.__table__.indexes
        if item.name == "uq_users_inn_normalized"
    )

    assert index.unique is True
    assert "trim" in str(index.expressions[0]).lower()
    where = str(index.dialect_options["postgresql"]["where"]).lower()
    assert "inn is not null" in where
    assert "trim(both from inn)" in where


def test_inn_identity_migration_fails_closed_on_duplicates():
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "a6d4f8c2e951_unique_normalized_user_inn.py"
    ).read_text(encoding="utf-8")

    assert "GROUP BY trim(inn)" in migration
    assert "HAVING count(*) > 1" in migration
    assert "Разрешите дубликаты вручную" in migration
    assert '"uq_users_inn_normalized"' in migration


def test_email_identity_migration_fails_closed_on_case_duplicates():
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "f4d9b2a6c731_case_insensitive_user_email.py"
    ).read_text(encoding="utf-8")

    assert "GROUP BY lower(email)" in migration
    assert "HAVING count(*) > 1" in migration
    assert "Разрешите дубликаты вручную" in migration
    assert '"uq_users_email_lower"' in migration


@pytest.mark.asyncio
async def test_insert_user_propagates_flush_failure_to_transaction_owner():
    class FailingSession(FakeSession):
        async def flush(self):
            self.flush_count += 1
            raise RuntimeError("database flush failed")

    session = FailingSession()
    with pytest.raises(RuntimeError, match="database flush failed"):
        await insert_user(
            session,
            {
                "email": "duplicate@example.com",
                "phone": "+10000000001",
                "full_name": "Duplicate User",
                "password": "a-secure-test-password",
                "entity_type": "individual",
            },
        )

    assert session.flush_count == 1
    assert session.refresh_count == 0


@pytest.mark.asyncio
async def test_update_user_flushes_mutation_before_refresh():
    session = FakeSession()

    class UserStub:
        full_name = "Before"

    user = UserStub()
    result = await update_user(session, user, {"full_name": "After"})

    assert result is user
    assert user.full_name == "After"
    assert session.flush_count == 1
    assert session.refresh_count == 1



@pytest.mark.asyncio
async def test_update_user_propagates_flush_failure_to_transaction_owner():
    class FailingSession(FakeSession):
        async def flush(self):
            self.flush_count += 1
            raise RuntimeError("ошибка обновления пользователя")

    session = FailingSession()

    class UserStub:
        full_name = "Before"

    with pytest.raises(RuntimeError, match="ошибка обновления пользователя"):
        await update_user(session, UserStub(), {"full_name": "After"})


@pytest.mark.asyncio
async def test_delete_user_propagates_database_failure():
    class FailingSession:
        async def execute(self, _statement):
            raise RuntimeError("ошибка удаления пользователя")

    class UserStub:
        id = "11111111-1111-4111-8111-111111111111"

    with pytest.raises(RuntimeError, match="ошибка удаления пользователя"):
        await delete_user(FailingSession(), UserStub())


@pytest.mark.asyncio
async def test_create_role_association_propagates_flush_failure():
    class FailingSession:
        def add(self, _obj):
            pass

        async def flush(self):
            raise RuntimeError("ошибка назначения роли")

    with pytest.raises(RuntimeError, match="ошибка назначения роли"):
        await create_user_role_association(
            FailingSession(),
            user_id="11111111-1111-4111-8111-111111111111",
            role_code="user",
        )


@pytest.mark.asyncio
async def test_delete_role_association_propagates_flush_failure():
    class FailingSession:
        async def delete(self, _obj):
            pass

        async def flush(self):
            raise RuntimeError("ошибка удаления роли")

    with pytest.raises(RuntimeError, match="ошибка удаления роли"):
        await delete_role_association(
            FailingSession(),
            object(),
        )



@pytest.mark.asyncio
async def test_super_admin_role_lookup_uses_for_update_lock():
    captured = {}

    class ScalarResult:
        def all(self):
            return [object(), object()]

    class Result:
        def scalars(self):
            return ScalarResult()

    class LockingSession:
        async def execute(self, statement):
            captured["statement"] = statement
            return Result()

    rows = await get_role_associations_for_update(
        LockingSession(),
        "super_admin",
    )

    assert len(rows) == 2
    assert "FOR UPDATE" in str(captured["statement"]).upper()
