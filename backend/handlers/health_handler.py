import asyncio

import redis.asyncio as redis
from fastapi import APIRouter, Response, status

from core.database import Database
from core.version import APP_VERSION
from settings import config


router = APIRouter(prefix="/health", tags=["Health"])


async def _redis_health_check() -> bool:
    client = redis.from_url(
        config.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
    )
    try:
        return bool(await client.ping())
    except Exception:
        return False
    finally:
        await client.aclose()


@router.get("/live")
async def liveness() -> dict:
    """Process liveness: no downstream dependency checks."""
    return {"status": "ok", "version": APP_VERSION}


@router.get("/ready")
async def readiness(response: Response) -> dict:
    """Readiness for serving requests and background sync work."""
    database_ok, redis_ok = await asyncio.gather(
        Database.health_check(),
        _redis_health_check(),
    )
    ready = database_ok and redis_ok
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if ready else "degraded",
        "version": APP_VERSION,
        "checks": {
            "database": "ok" if database_ok else "error",
            "redis": "ok" if redis_ok else "error",
        },
    }
