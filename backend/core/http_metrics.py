from datetime import datetime, timedelta, timezone

import redis.asyncio as redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from core.logger import setup_logger
from core.ops_config import ops_config
from settings import config


logger = setup_logger(__name__, "http_metrics.log")
_metrics_redis = redis.from_url(
    config.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)
_METRIC_TTL_SECONDS = 2 * 60 * 60


def _bucket(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return current.strftime("%Y%m%d%H%M")


def http_metric_keys(bucket: str) -> tuple[str, str]:
    prefix = f"ops:http:{bucket}"
    return f"{prefix}:total", f"{prefix}:5xx"


async def record_http_status(status_code: int, *, now: datetime | None = None) -> None:
    if not ops_config.HTTP_METRICS_ENABLED:
        return

    total_key, errors_key = http_metric_keys(_bucket(now))
    try:
        pipe = _metrics_redis.pipeline(transaction=False)
        pipe.incr(total_key)
        pipe.expire(total_key, _METRIC_TTL_SECONDS)
        if status_code >= 500:
            pipe.incr(errors_key)
            pipe.expire(errors_key, _METRIC_TTL_SECONDS)
        await pipe.execute()
    except Exception:
        # Metrics must never turn an otherwise healthy request into a failure.
        logger.exception("Unable to persist HTTP operational metric")


async def read_http_counters(
    window_minutes: int,
    *,
    now: datetime | None = None,
) -> tuple[int, int]:
    if not ops_config.HTTP_METRICS_ENABLED:
        return 0, 0

    current = now or datetime.now(timezone.utc)
    keys: list[str] = []
    for offset in range(window_minutes):
        bucket = _bucket(current - timedelta(minutes=offset))
        keys.extend(http_metric_keys(bucket))

    values = await _metrics_redis.mget(keys)
    total = 0
    errors = 0
    for index in range(0, len(values), 2):
        total += int(values[index] or 0)
        errors += int(values[index + 1] or 0)
    return total, errors


class HTTPMetricsMiddleware(BaseHTTPMiddleware):
    """Record minute-bucket request and 5xx counters in shared Redis."""

    async def dispatch(self, request: Request, call_next) -> Response:
        try:
            response = await call_next(request)
        except Exception:
            await record_http_status(500)
            raise

        await record_http_status(response.status_code)
        return response
