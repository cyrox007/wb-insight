import asyncio
import hashlib
import json

import httpx
import redis.asyncio as redis

from celery_app import celery_app
from core.database_celery import get_session
from core.logger import setup_logger
from core.ops_config import ops_config
from services.operational_monitoring_service import build_operational_snapshot
from settings import config


logger = setup_logger(__name__, "operations_monitor.log")
_alert_redis = redis.from_url(
    config.REDIS_URL,
    encoding="utf-8",
    decode_responses=True,
)
_ALERT_FINGERPRINT_KEY = "ops:alert:last-fingerprint"


def _alert_fingerprint(snapshot: dict) -> str:
    reduced = {
        "status": snapshot.get("status"),
        "checks": {
            name: {
                key: value
                for key, value in check.items()
                if key in {"status", "count", "errors", "requests", "rate", "reason"}
            }
            for name, check in snapshot.get("checks", {}).items()
        },
    }
    raw = json.dumps(reduced, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _should_send_webhook(snapshot: dict) -> bool:
    fingerprint = _alert_fingerprint(snapshot)
    try:
        previous = await _alert_redis.get(_ALERT_FINGERPRINT_KEY)
        if previous == fingerprint:
            return False
        await _alert_redis.set(
            _ALERT_FINGERPRINT_KEY,
            fingerprint,
            ex=ops_config.ALERT_REPEAT_SECONDS,
        )
        return True
    except Exception:
        # Alert delivery must not fail because deduplication storage is down.
        logger.exception("Unable to deduplicate operations alert")
        return True


async def _send_webhook(snapshot: dict) -> None:
    if not ops_config.ALERT_WEBHOOK_URL:
        return
    if not await _should_send_webhook(snapshot):
        return

    payload = {
        "event": "wb_insight_operations_alert",
        "status": snapshot["status"],
        "version": snapshot["version"],
        "generated_at": snapshot["generated_at"],
        "checks": snapshot["checks"],
    }
    try:
        async with httpx.AsyncClient(
            timeout=ops_config.ALERT_WEBHOOK_TIMEOUT_SECONDS
        ) as client:
            response = await client.post(ops_config.ALERT_WEBHOOK_URL, json=payload)
            response.raise_for_status()
    except Exception:
        logger.exception("Operations alert webhook delivery failed")


async def run_operations_check() -> dict:
    session = await get_session()
    try:
        snapshot = await build_operational_snapshot(session)
        if snapshot["status"] != "ok":
            logger.warning(
                "OPERATIONS_ALERT %s",
                json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
            )
            await _send_webhook(snapshot)
        return snapshot
    finally:
        await session.close()


@celery_app.task(name="tasks.processors.operations_monitor.run")
def run() -> dict:
    return asyncio.run(run_operations_check())
