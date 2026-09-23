import pytest

from services.user_service import (
    create_user_role_association,
    delete_role_association,
    delete_user,
    get_role_associations_for_update,
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
    assert user.inn is None
    assert user.kpp is None
    assert user.legal_address is None


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
