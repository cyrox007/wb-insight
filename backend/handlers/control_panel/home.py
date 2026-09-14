from decimal import Decimal, InvalidOperation

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Response, status, Request

from core.authorization import require_admin
from core.logger import setup_logger
from core.dependencies import get_db_session
from services.tariff_service import get_tariffs_list, insert_tariff
from services.user_service import get_user_count
from utils.responce_helps import response_success, response_error

router = APIRouter(
    prefix='/control-panel',
    tags=['Control Panel'],
    dependencies=[Depends(require_admin)],
)
logger = setup_logger(__name__)


@router.get('/')
async def get_control_panel(db_session: AsyncSession = Depends(get_db_session)):
    user_count = await get_user_count(db_session)
    return response_success(
        user_count=user_count
    )
