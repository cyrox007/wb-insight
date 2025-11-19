# core/dependencies.py
from sqlalchemy.ext.asyncio import AsyncSession
from core.logger import setup_logger
from database import Database
from fastapi import HTTPException

logger = setup_logger(__name__)

async def get_db_session() -> AsyncSession: # type: ignore
    """
    FastAPI dependency для получения сессии БД
    """
    db_session = await Database.get_session()
    try:
        yield db_session # type: ignore
        await db_session.commit()
    except Exception as e:
        raise
    finally:
        await db_session.close()