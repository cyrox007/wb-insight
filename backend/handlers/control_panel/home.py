from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, Request

from core.access_control import Permission
from core.authorization import require_permission
from core.dependencies import get_db_session
from models.users_model import User
from services.user_service import get_user_count
from utils.responce_helps import response_success


router = APIRouter(
    prefix='/control-panel',
    tags=['Control Panel'],
    dependencies=[Depends(require_permission(Permission.CONTROL_PANEL_ACCESS))],
)


async def _account_health(db_session: AsyncSession) -> dict[str, int]:
    result = await db_session.execute(
        select(
            func.count(User.id).label("total"),
            func.count(User.id).filter(User.is_active.is_(True)).label("active"),
            func.count(User.id).filter(User.is_active.is_(False)).label("inactive"),
            func.count(User.id).filter(User.email_verified_at.is_not(None)).label("verified"),
            func.count(User.id).filter(User.email_verified_at.is_(None)).label("unverified"),
            func.count(User.id).filter(User.is_staff.is_(True)).label("staff"),
        )
    )
    row = result.one()
    return {
        "total": int(row.total or 0),
        "active": int(row.active or 0),
        "inactive": int(row.inactive or 0),
        "verified": int(row.verified or 0),
        "unverified": int(row.unverified or 0),
        "staff": int(row.staff or 0),
    }


@router.get('/')
async def get_control_panel(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
):
    permissions = set(getattr(request.state, "permissions", set()))
    user_count = (
        await get_user_count(db_session)
        if Permission.USERS_READ.value in permissions
        else None
    )
    return response_success(
        user_count=user_count,
        account_health=await _account_health(db_session),
        permissions=sorted(permissions),
    )
