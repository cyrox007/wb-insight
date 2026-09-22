import asyncio
import math

from redis.asyncio import Redis
from redis.asyncio import from_url as redis_from_url
from redis.exceptions import RedisError

from core.logger import setup_logger


logger = setup_logger(__name__, "wb_client.log")


_COOLDOWN_MAX_TTL_SCRIPT = """
local current = redis.call('PTTL', KEYS[1])
local requested = tonumber(ARGV[1])
if current < requested then
    redis.call('PSETEX', KEYS[1], requested, '1')
    return requested
end
return current
"""


class DistributedRateLimiter:
    """Координирует интервалы запросов Wildberries между процессами через Redis.

    Ключ строится из внутреннего идентификатора подключения и логического имени
    маршрута. Сырые и зашифрованные токены маркетплейса никогда не становятся
    ключами Redis. Если Redis недоступен, ограничитель пропускает запрос:
    недоступность профилактического лимитера не должна полностью блокировать
    прямые HTTP-сценарии.
    """

    def __init__(
        self,
        redis_url: str,
        prefix: str = "wb:rate-limit",
        *,
        redis_client: Redis | None = None,
    ) -> None:
        self._redis: Redis = redis_client or redis_from_url(
            redis_url,
            decode_responses=True,
        )
        self._prefix = prefix

    def _key(self, credential_id: str, endpoint: str) -> str:
        safe_endpoint = endpoint.replace(" ", "_")
        return f"{self._prefix}:{credential_id}:{safe_endpoint}"

    async def acquire(
        self,
        credential_id: str,
        endpoint: str,
        min_interval_seconds: float,
    ) -> None:
        if min_interval_seconds <= 0:
            return

        key = self._key(credential_id, endpoint)
        ttl_ms = max(1, math.ceil(min_interval_seconds * 1000))

        while True:
            try:
                acquired = await self._redis.set(key, "1", nx=True, px=ttl_ms)
                if acquired:
                    return

                remaining_ms = await self._redis.pttl(key)
            except RedisError as exc:
                logger.warning(
                    "Распределённый ограничитель запросов Wildberries недоступен; запрос продолжится без предварительного ограничения: %s",
                    type(exc).__name__,
                )
                return

            if remaining_ms <= 0:
                await asyncio.sleep(0)
                continue

            await asyncio.sleep(max(remaining_ms / 1000.0, 0.01))

    async def cooldown(
        self,
        credential_id: str,
        endpoint: str,
        seconds: float,
    ) -> None:
        """Публикует паузу, не сокращая более длинную параллельную паузу."""
        if seconds <= 0:
            return

        key = self._key(credential_id, endpoint)
        ttl_ms = max(1, math.ceil(seconds * 1000))
        try:
            await self._redis.eval(
                _COOLDOWN_MAX_TTL_SCRIPT,
                1,
                key,
                ttl_ms,
            )
        except RedisError as exc:
            logger.warning(
                "Не удалось опубликовать паузу ограничения запросов Wildberries в Redis: %s",
                type(exc).__name__,
            )

    async def aclose(self) -> None:
        await self._redis.aclose()
