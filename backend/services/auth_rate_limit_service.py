"""Ограничение частоты публичных запросов аутентификации."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

from core.logger import setup_logger
from settings import config


logger = setup_logger(__name__)


@dataclass(frozen=True)
class RateLimitRule:
    """Лимит количества запросов в фиксированном окне времени."""

    limit: int
    window_seconds: int


@dataclass(frozen=True)
class RateLimitDecision:
    """Результат проверки лимита."""

    allowed: bool
    retry_after_seconds: int = 0


class AuthRateLimitUnavailable(RuntimeError):
    """Хранилище production rate-limit временно недоступно."""


_LUA_INCREMENT = """
local value = redis.call('INCR', KEYS[1])
if value == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {value, ttl}
"""

_redis: Redis | None = None
_local_lock = asyncio.Lock()
_local_counters: dict[str, tuple[int, float]] = {}


def _get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(
            config.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


def _opaque_fragment(value: str) -> str:
    """Создаёт непрозрачный HMAC-фрагмент без хранения исходных персональных данных."""

    normalized = str(value or "").strip().lower().encode("utf-8")
    secret = str(config.SECRET_KEY).encode("utf-8")
    return hmac.new(secret, normalized, hashlib.sha256).hexdigest()


def _safe_ip(value: str | None) -> str:
    candidate = str(value or "").strip()
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return "unknown"


def client_ip(request: Request) -> str:
    """Возвращает клиентский IP, доверяя X-Real-IP только локальному reverse proxy."""

    peer = _safe_ip(request.client.host if request.client else None)
    if peer not in {"127.0.0.1", "::1"}:
        return peer

    forwarded = _safe_ip(request.headers.get("x-real-ip"))
    return forwarded if forwarded != "unknown" else peer


def _key(action: str, dimension: str, value: str) -> str:
    return f"wb:auth-rate:{action}:{dimension}:{_opaque_fragment(value)}"


async def _redis_increment(key: str, rule: RateLimitRule) -> RateLimitDecision:
    try:
        raw = await _get_redis().eval(
            _LUA_INCREMENT,
            1,
            key,
            int(rule.window_seconds),
        )
    except RedisError as exc:
        logger.error("Хранилище ограничения частоты авторизации недоступно")
        raise AuthRateLimitUnavailable from exc

    count = int(raw[0])
    ttl = max(int(raw[1]), 1)
    return RateLimitDecision(
        allowed=count <= rule.limit,
        retry_after_seconds=0 if count <= rule.limit else ttl,
    )


async def _local_increment(key: str, rule: RateLimitRule) -> RateLimitDecision:
    """Локальный fallback разрешён только вне production."""

    now = time.monotonic()
    async with _local_lock:
        count, expires_at = _local_counters.get(
            key,
            (0, now + rule.window_seconds),
        )
        if expires_at <= now:
            count = 0
            expires_at = now + rule.window_seconds
        count += 1
        _local_counters[key] = (count, expires_at)

    retry_after = max(int(expires_at - now), 1)
    return RateLimitDecision(
        allowed=count <= rule.limit,
        retry_after_seconds=0 if count <= rule.limit else retry_after,
    )


async def _check_key(key: str, rule: RateLimitRule) -> RateLimitDecision:
    try:
        return await _redis_increment(key, rule)
    except AuthRateLimitUnavailable:
        if config.IS_PRODUCTION:
            raise
        logger.warning(
            "Redis недоступен; вне production используется локальный лимитер авторизации"
        )
        return await _local_increment(key, rule)


async def check_auth_rate_limit(
    request: Request,
    *,
    action: str,
    ip_rule: RateLimitRule,
    identity: Optional[str] = None,
    identity_rule: Optional[RateLimitRule] = None,
) -> RateLimitDecision:
    """Проверяет IP и при необходимости идентификатор без сохранения PII в Redis-ключах."""

    ip_decision = await _check_key(
        _key(action, "ip", client_ip(request)),
        ip_rule,
    )
    if not ip_decision.allowed:
        return ip_decision

    if not identity or identity_rule is None:
        return ip_decision

    identity_decision = await _check_key(
        _key(action, "identity", identity),
        identity_rule,
    )
    return identity_decision
