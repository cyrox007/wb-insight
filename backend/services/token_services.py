from datetime import datetime, timedelta, timezone
from typing import List, Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from models.tokens import APITokens, Marketplace
from utils.token_crypto import encrypt_token

logger = setup_logger(__name__)


async def get_user_token_count(session: AsyncSession, user_id: str) -> int:
    """ получаем кол-во токенов добавленных пользователем """
    result = await session.execute(
        select(APITokens).where(APITokens.user_id == user_id)
    )
    return len(result.scalars().all())

async def insert_token(
        session: AsyncSession, 
        user_id: str, 
        raw_token: str,
        marketplace_code: str = 'wb',
        token_type: str = 'personal',
        label: str = 'Токен для аналитики'
    ) -> Optional[APITokens]:
    """ добавляем токен """
    token = APITokens(
        user_id=user_id,
        marketplace=Marketplace.WILDBERRIES if marketplace_code == 'wb' else marketplace_code,
        token_type=token_type,
        encrypted_token=encrypt_token(raw_token),
        label=label
    )

    # Устанавливаем issued_at вручную (если нужно) или оставляем по умолчанию
    # Устанавливаем expires_at
    token.issued_at = datetime.now(timezone.utc)
    token.expires_at = token.issued_at + timedelta(days=180)

    try:
        # Сохраняем
        session.add(token)
        await session.commit()
        await session.refresh(token)
        return token
    except Exception as e:
        await session.rollback()
        logger.error(f"Ошибка при добавлении токена: {e}")
        return None
    

async def get_tokens_by_user_id(session: AsyncSession, user_id: str) -> Sequence[APITokens]:
    """ получаем токен по user_id """
    result = await session.execute(
        select(APITokens).where(APITokens.user_id == user_id)
    )
    return result.scalars().all()

async def get_token_by_id(session: AsyncSession, token_id: str) -> Optional[APITokens]:
    """ получаем токен по id """
    result = await session.execute(
        select(APITokens).where(APITokens.id == token_id)
    )
    return result.scalar_one_or_none()

async def delete_token(session: AsyncSession, token: APITokens) -> bool:
    """ удаляем токен """
    try:
        await session.delete(token)
        await session.commit()
        return True
    except Exception as e:
        await session.rollback()
        logger.error(f"Ошибка при удалении токена: {e}")
        return False