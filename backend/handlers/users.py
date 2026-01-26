from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends

from core.dependencies import get_db_session
from core.logger import setup_logger


routers = APIRouter(prefix="/users", tags=["users"])

logger = setup_logger(__name__)

@routers.get('/')
async def get_users(db_session: AsyncSession = Depends(get_db_session)):
    # print(db_session)
    return {}