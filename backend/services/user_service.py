from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from schemas.users import UserCreateRequest
from models.users import User, user_roles
from utils.hashed_password import hash_password


async def insert_user(session: AsyncSession, user_data: UserCreateRequest):
    new_user = User(
        id=uuid4(),
        email=user_data.email,
        phone=user_data.phone,
        full_name=user_data.full_name,
        hashed_password=hash_password(user_data.password),
        entity_type=user_data.entity_type.value,
        inn=user_data.inn,
        kpp=user_data.kpp,
        legal_address=user_data.legal_address,
        timezone=user_data.timezone,
        created_at=datetime.utcnow(),
        is_active=True,
        is_staff=False
    )

    session.add(new_user)
    await session.commit()

    return new_user

async def set_user_role(session: AsyncSession, new_user, role_type: str = 'user'):
    await session.execute(
        user_roles.insert().values(
            user_id=new_user.id,
            role=role_type,
            assigned_at=datetime.utcnow()
        )
    )
    await session.commit()

async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    result = await session.execute(
        select(User).where(User.email == email)
    )
    return result.scalar_one_or_none()

async def get_user_by_phone(session: AsyncSession, phone: str) -> Optional[User]:
    result = await session.execute(
        select(User).where(User.phone == phone)
    )
    return result.scalar_one_or_none()