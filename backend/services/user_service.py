from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.logger import setup_logger
from schemas.users import UserCreateRequest
from models.users import User, UserRoleAssociation
from utils.hashed_password import hash_password


logger = setup_logger(__name__)

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

async def get_user_by_uuid(session: AsyncSession, user_id: str) -> Optional[User]:
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()

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

async def get_user_count(session: AsyncSession) -> int:
    result = await session.execute(
        select(User)
    )
    return len(result.scalars().all())

async def get_user_list(session: AsyncSession, offset: int = 0, limit: int = 10):
    stmt = (
        select(User)
        .options(selectinload(User.roles))  # ← загружает роли отдельным запросом
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    users = result.scalars().all()
    return users

async def update_user(session: AsyncSession, user: User, user_data: dict) -> Optional[User]:
    try:
        for key, value in user_data.items():
            setattr(user, key, value)
        await session.commit()
        await session.refresh(user)
        return user
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        await session.rollback()
        return None

async def delete_user(session: AsyncSession, user: User):
    try:
        await session.delete(user)
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        await session.rollback()
        return False
    

async def get_user_role_association(session: AsyncSession, user_id: str):
    result = await session.execute(
        select(UserRoleAssociation).where(UserRoleAssociation.user_id == user_id)
    )
    return result.scalar_one_or_none()

async def get_user_role_association_by_code(session: AsyncSession, user_id: str, role_code: str) -> Optional[UserRoleAssociation]:
    result = await session.execute(
        select(UserRoleAssociation).where(
            UserRoleAssociation.user_id == user_id, 
            UserRoleAssociation.role == role_code
        )
    )
    return result.scalar_one_or_none()

async def create_user_role_association(session: AsyncSession, user_id: str, role_code='user', assigned_by=''):
    user_role_association = UserRoleAssociation(
        user_id=user_id,
        role=role_code,
        assigned_by=assigned_by if assigned_by else None
    )
    try:
        session.add(user_role_association)
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Error creating user role association: {e}")
        await session.rollback()
        return False
    
async def delete_role_association(session: AsyncSession, target_role: UserRoleAssociation):
    try:
        await session.delete(target_role)
        await session.commit()
        return True
    except Exception as e:
        logger.error(f"Error deleting role association: {e}")
        await session.rollback()
        return False