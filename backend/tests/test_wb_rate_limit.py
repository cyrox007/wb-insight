import pytest

from integrations.wildberries.rate_limit import DistributedRateLimiter


class FakeRedis:
    def __init__(self):
        self.eval_calls = []
        self.closed = False

    async def eval(self, script, numkeys, key, ttl_ms):
        self.eval_calls.append((script, numkeys, key, ttl_ms))
        return ttl_ms

    async def aclose(self):
        self.closed = True


@pytest.mark.asyncio
async def test_cooldown_uses_atomic_max_ttl_script():
    redis = FakeRedis()
    limiter = DistributedRateLimiter(
        "redis://unused",
        redis_client=redis,  # type: ignore[arg-type]
    )

    await limiter.cooldown(
        "credential-123",
        "analytics.stocks_warehouses",
        2.5,
    )
    await limiter.aclose()

    assert len(redis.eval_calls) == 1
    script, numkeys, key, ttl_ms = redis.eval_calls[0]
    assert numkeys == 1
    assert key == "wb:rate-limit:credential-123:analytics.stocks_warehouses"
    assert ttl_ms == 2500
    assert "PTTL" in script
    assert "PSETEX" in script
    assert "current < requested" in script
    assert redis.closed is True
