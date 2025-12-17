# core/dependencies.py
from sqlalchemy.ext.asyncio import AsyncSession
from core.logger import setup_logger
from database import Database
from fastapi import HTTPException, Request

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

def require_permission(permission: str):
    async def permission_checker(request: Request):
        # Получаем uid из запроса (зависит от вашей аутентификации)
        # Например, если используете JWT:
        # uid = request.state.user_id
        
        # Пример: предположим, uid хранится в заголовке
        uid = request.headers.get("X-User-UID")
        if not uid:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Проверяем разрешение в БД
        # has_permission = await check_permission_in_db(uid, permission)
        
        # if not has_permission:
        #     raise HTTPException(status_code=403, detail="Permission denied")
        
        return True
    
    return permission_checker