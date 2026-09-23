from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.logger import setup_logger
from models.users_model import User, UserRoleAssociation
from utils.hashed_password import hash_password


logger = setup_logger(__name__)


async def insert_user(session: AsyncSession, user_data: dict):
    if not user_data:
        logger.warning("Пустые данные пользователя")
        return None

    for field in ['email', 'phone', 'full_name', 'password']:
        if not user_data.get(field):
            logger.warning(f"Отсутствует обязательное поле: {field}")
            return None

    new_user = User(
        id=uuid4(),
        email=user_data['email'],
        phone=user_data['phone'],
        full_name=user_data['full_name'],
        hashed_password=hash_password(user_data['password']),
        entity_type=user_data.get('entity_type', 'individual'),
        inn=user_data.get('inn'),
        kpp=user_data.get('kpp'),
        legal_address=user_data.get('legal_address'),
        timezone=user_data.get('timezone') or 'Europe/Moscow',
        created_at=datetime.now(timezone.utc),
        is_active=True,
        is_staff=False,
    )

    session.add(new_user)
    # Ошибки сохранения должны дойти до владельца request-транзакции.
    # Скрывать ошибку flush нельзя: сессия после неё остаётся аварийной.
    await session.flush()
    await session.refresh(new_user)

    logger.info(f"Пользователь создан: {new_user.id}")
    return new_user


async def get_user_by_uuid(session: AsyncSession, user_id: UUID) -> Optional[User]:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_phone(session: AsyncSession, phone: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.phone == phone))
    return result.scalar_one_or_none()


async def get_user_by_inn(session: AsyncSession, inn: str) -> Optional[User]:
    result = await session.execute(select(User).where(User.inn == inn))
    return result.scalar_one_or_none()


async def get_user_count(session: AsyncSession) -> int:
    result = await session.execute(select(func.count()).select_from(User))
    return result.scalar_one()


async def get_user_list(
    session: AsyncSession,
    offset: int = 0,
    limit: int | None = 10,
) -> list[User]:
    query = select(User).options(selectinload(User.roles)).order_by(User.created_at.desc())
    if limit is not None:
        query = query.offset(offset).limit(limit)

    result = await session.execute(query)
    return list(result.scalars().unique().all())


async def update_user(
    session: AsyncSession,
    user: User,
    user_data: dict,
) -> User:
    for key, value in user_data.items():
        setattr(user, key, value)
    await session.flush()
    await session.refresh(user)
    return user


async def delete_user(session: AsyncSession, user: User) -> bool:
    """Необратимо удаляет пользователя, оставляя каскады базе данных."""
    result = await session.execute(
        delete(User).where(User.id == user.id).returning(User.id)
    )
    return result.scalar_one_or_none() is not None


async def get_user_role_association(session: AsyncSession, user_id: str):
    result = await session.execute(
        select(UserRoleAssociation).where(UserRoleAssociation.user_id == user_id)
    )
    return result.scalars().first()


async def get_user_role_association_by_code(
    session: AsyncSession,
    user_id: str,
    role_code: str,
) -> Optional[UserRoleAssociation]:
    result = await session.execute(
        select(UserRoleAssociation).where(
            UserRoleAssociation.user_id == user_id,
            UserRoleAssociation.role == role_code,
        )
    )
    return result.scalar_one_or_none()


async def count_user_role_associations_by_code(
    session: AsyncSession,
    role_code: str,
) -> int:
    """Возвращает количество назначений указанной системной роли."""
    result = await session.execute(
        select(func.count(UserRoleAssociation.id)).where(
            UserRoleAssociation.role == role_code
        )
    )
    return int(result.scalar_one() or 0)


async def create_user_role_association(
    session: AsyncSession,
    user_id: str,
    role_code: str = 'user',
    assigned_by: str = '',
) -> bool:
    user_role_association = UserRoleAssociation(
        user_id=user_id,
        role=role_code,
        assigned_by=assigned_by if assigned_by else None,
    )
    session.add(user_role_association)
    await session.flush()
    return True


async def delete_role_association(
    session: AsyncSession,
    target_role: UserRoleAssociation,
) -> bool:
    await session.delete(target_role)
    await session.flush()
    return True


async def get_user_tax_rate(session: AsyncSession, user_id: UUID) -> float:
    result = await session.execute(select(User.tax_rate).where(User.id == user_id))
    return result.scalar_one_or_none() or 0.2
