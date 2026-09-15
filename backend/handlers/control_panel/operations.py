from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.authorization import require_super_admin
from core.dependencies import get_db_session
from services.operational_monitoring_service import build_operational_snapshot


router = APIRouter(
    prefix="/control-panel/operations",
    tags=["Control Panel Operations"],
    dependencies=[Depends(require_super_admin)],
)


@router.get("/health")
async def get_operational_health(
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return aggregate release/operations signals without seller secrets or PII."""
    return await build_operational_snapshot(db_session)
