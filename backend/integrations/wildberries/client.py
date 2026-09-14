import asyncio
import random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from core.logger import setup_logger
from integrations.wildberries import endpoints
from integrations.wildberries.rate_limit import DistributedRateLimiter
from models.tokens_model import APIToken
from settings import config
from utils.token_crypto import decrypt_token


logger = setup_logger(__name__, "wb_client.log")


class WBAPIError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        endpoint: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.endpoint = endpoint
        self.status_code = status_code


class WBAuthError(WBAPIError):
    pass


class WBPermissionError(WBAPIError):
    pass


class WBRateLimitError(WBAPIError):
    pass


class WBClient:
    """Wildberries HTTP client with bounded retry and distributed throttling."""

    def __init__(
        self,
        token: APIToken,
        *,
        http_client: httpx.AsyncClient | None = None,
        rate_limiter: DistributedRateLimiter | None = None,
    ) -> None:
        self._encrypted_token = token.encrypted_token
        self._user_id = str(token.user_id)
        self._credential_id = str(token.id)
        self._client = http_client or httpx.AsyncClient(timeout=60.0)
        self._rate_limiter = rate_limiter or DistributedRateLimiter(config.REDIS_URL)
        self._closed = False

    async def __aenter__(self) -> "WBClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            await self._client.aclose()
        finally:
            await self._rate_limiter.aclose()

    def _get_token(self) -> str:
        return decrypt_token(self._encrypted_token, self._user_id)

    @staticmethod
    def _endpoint_interval(endpoint: str) -> float:
        return {
            "finance.sales_report_detailed": config.WB_FINANCE_MIN_INTERVAL_SECONDS,
            "analytics.stocks_warehouses": config.WB_STOCKS_MIN_INTERVAL_SECONDS,
            "content.cards_list": config.WB_CONTENT_CARDS_MIN_INTERVAL_SECONDS,
            "statistics.orders": config.WB_OPERATIONAL_MIN_INTERVAL_SECONDS,
            "statistics.sales": config.WB_OPERATIONAL_MIN_INTERVAL_SECONDS,
            "promotion.campaigns": config.WB_ADVERT_CAMPAIGNS_MIN_INTERVAL_SECONDS,
            "promotion.fullstats": config.WB_ADVERT_STATS_MIN_INTERVAL_SECONDS,
        }.get(endpoint, config.WB_API_MIN_INTERVAL_SECONDS)

    @staticmethod
    def _retry_after_seconds(response: httpx.Response) -> float | None:
        value = response.headers.get("Retry-After")
        if not value:
            return None

        try:
            return max(0.0, float(value))
        except ValueError:
            pass

        try:
            retry_at = parsedate_to_datetime(value)
            if retry_at.tzinfo is None:
                retry_at = retry_at.replace(tzinfo=timezone.utc)
            return max(
                0.0,
                (retry_at - datetime.now(timezone.utc)).total_seconds(),
            )
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def _backoff_seconds(attempt: int) -> float:
        base = config.WB_API_BACKOFF_BASE_SECONDS * (2 ** max(0, attempt - 1))
        capped = min(base, config.WB_API_MAX_BACKOFF_SECONDS)
        jitter = random.uniform(0.0, min(1.0, capped * 0.2))
        return min(capped + jitter, config.WB_API_MAX_BACKOFF_SECONDS)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> Any:
        last_transport_error: Exception | None = None

        for attempt in range(1, config.WB_API_MAX_ATTEMPTS + 1):
            await self._rate_limiter.acquire(
                self._credential_id,
                endpoint,
                self._endpoint_interval(endpoint),
            )

            token = self._get_token()
            try:
                response = await self._client.request(
                    method=method,
                    url=url,
                    headers={"Authorization": token},
                    params=params,
                    json=json_data,
                )
            except httpx.TransportError as exc:
                last_transport_error = exc
                if attempt >= config.WB_API_MAX_ATTEMPTS:
                    raise WBAPIError(
                        "Wildberries transport error after retry budget was exhausted",
                        endpoint=endpoint,
                    ) from exc

                delay = self._backoff_seconds(attempt)
                logger.warning(
                    "WB transport error endpoint=%s attempt=%s/%s; retrying",
                    endpoint,
                    attempt,
                    config.WB_API_MAX_ATTEMPTS,
                )
                await asyncio.sleep(delay)
                continue
            finally:
                del token

            if response.status_code == 204:
                return []

            if response.status_code == 401:
                logger.warning(
                    "WB authorization rejected endpoint=%s status=%s",
                    endpoint,
                    response.status_code,
                )
                raise WBAuthError(
                    "Wildberries authorization rejected the marketplace credential",
                    endpoint=endpoint,
                    status_code=response.status_code,
                )

            if response.status_code == 403:
                logger.warning(
                    "WB permission denied endpoint=%s status=%s",
                    endpoint,
                    response.status_code,
                )
                raise WBPermissionError(
                    "Wildberries credential lacks permission for this API category",
                    endpoint=endpoint,
                    status_code=response.status_code,
                )

            if response.status_code == 429:
                retry_after = self._retry_after_seconds(response)
                delay = retry_after if retry_after is not None else self._backoff_seconds(attempt)
                delay = min(max(delay, 0.01), config.WB_API_MAX_BACKOFF_SECONDS)

                await self._rate_limiter.cooldown(
                    self._credential_id,
                    endpoint,
                    delay,
                )

                if attempt >= config.WB_API_MAX_ATTEMPTS:
                    raise WBRateLimitError(
                        "Wildberries rate limit retry budget was exhausted",
                        endpoint=endpoint,
                        status_code=429,
                    )

                logger.warning(
                    "WB rate limited endpoint=%s attempt=%s/%s cooldown=%.2fs",
                    endpoint,
                    attempt,
                    config.WB_API_MAX_ATTEMPTS,
                    delay,
                )
                await asyncio.sleep(delay)
                continue

            if 500 <= response.status_code <= 599:
                if attempt >= config.WB_API_MAX_ATTEMPTS:
                    raise WBAPIError(
                        "Wildberries server error after retry budget was exhausted",
                        endpoint=endpoint,
                        status_code=response.status_code,
                    )

                delay = self._backoff_seconds(attempt)
                logger.warning(
                    "WB server error endpoint=%s status=%s attempt=%s/%s; retrying",
                    endpoint,
                    response.status_code,
                    attempt,
                    config.WB_API_MAX_ATTEMPTS,
                )
                await asyncio.sleep(delay)
                continue

            if not response.is_success:
                logger.warning(
                    "WB request rejected endpoint=%s status=%s",
                    endpoint,
                    response.status_code,
                )
                raise WBAPIError(
                    "Wildberries API rejected the request",
                    endpoint=endpoint,
                    status_code=response.status_code,
                )

            try:
                return response.json()
            except ValueError as exc:
                logger.warning("WB returned invalid JSON endpoint=%s", endpoint)
                raise WBAPIError(
                    "Wildberries returned an invalid JSON response",
                    endpoint=endpoint,
                    status_code=response.status_code,
                ) from exc

        raise WBAPIError(
            "Wildberries request failed",
            endpoint=endpoint,
        ) from last_transport_error

    async def get_realization(self, payload: dict[str, Any] | None = None):
        request_body = dict(payload or {})
        request_body.setdefault("limit", 100000)
        request_body.setdefault("rrdId", 0)

        return await self._request(
            "POST",
            endpoints.REALIZATION_V2,
            endpoint="finance.sales_report_detailed",
            json_data=request_body,
        )

    async def get_stock(self, payload: dict[str, Any] | None = None):
        request_body = dict(payload or {})
        request_body.setdefault("limit", 250000)
        request_body.setdefault("offset", 0)

        return await self._request(
            "POST",
            endpoints.STOCKS_V2,
            endpoint="analytics.stocks_warehouses",
            json_data=request_body,
        )

    async def get_products(self, payload: dict[str, Any] | None = None):
        return await self._request(
            "POST",
            endpoints.PRODUCTS,
            endpoint="content.cards_list",
            json_data=payload or {},
        )

    async def get_orders(self, payload: dict[str, Any] | None = None):
        params = dict(payload or {})
        params.setdefault("flag", 0)
        return await self._request(
            "GET",
            f"{config.WB_API_BASE_URL}/api/v1/supplier/orders",
            endpoint="statistics.orders",
            params=params,
        )

    async def get_sales(self, payload: dict[str, Any] | None = None):
        params = dict(payload or {})
        params.setdefault("flag", 0)
        return await self._request(
            "GET",
            f"{config.WB_API_BASE_URL}/api/v1/supplier/sales",
            endpoint="statistics.sales",
            params=params,
        )

    async def get_advert_campaigns(self, payload: dict[str, Any] | None = None):
        return await self._request(
            "GET",
            endpoints.ADVERT_CAMPAIGNS,
            endpoint="promotion.campaigns",
            params=payload or {},
        )

    async def get_advert_stats(self, payload: dict[str, Any] | None = None):
        return await self._request(
            "GET",
            endpoints.ADVERT_STATS,
            endpoint="promotion.fullstats",
            params=payload or {},
        )
