import pytest

from services.user_service import insert_user, update_user


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
