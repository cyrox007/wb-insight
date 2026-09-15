import httpx

from integrations.wildberries.token_metadata import (
    WBTokenMetadata,
    WBTokenValidationError,
)


WB_COMMON_PING_URL = "https://common-api.wildberries.ru/ping"


async def validate_wb_token_live(
    raw_token: str,
    metadata: WBTokenMetadata,
    *,
    service_secret: str | None = None,
    http_client: httpx.AsyncClient | None = None,
) -> None:
    """Verify with WB that a credential is active and accepted server-side."""

    headers = {"Authorization": f"Bearer {raw_token.strip()}"}
    if metadata.token_type == "service":
        secret = (service_secret or "").strip()
        if not secret:
            raise WBTokenValidationError(
                "WB_SERVICE_SECRET_NOT_CONFIGURED",
                "На сервере не настроен сервисный секрет Wildberries.",
                status_code=503,
            )
        headers["X-Client-Secret"] = secret

    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(timeout=10.0)
    try:
        try:
            response = await client.get(WB_COMMON_PING_URL, headers=headers)
        except httpx.TransportError as exc:
            raise WBTokenValidationError(
                "WB_TOKEN_VALIDATION_UNAVAILABLE",
                (
                    "Wildberries временно недоступен для проверки токена. "
                    "Повторите подключение позже."
                ),
                status_code=503,
            ) from exc

        if response.status_code == 200:
            return

        if response.status_code == 401:
            raise WBTokenValidationError(
                "WB_TOKEN_REJECTED",
                (
                    "Wildberries отклонил токен. Проверьте, что он активен, "
                    "не отозван и срок действия не истёк."
                ),
            )

        if response.status_code == 403:
            if metadata.token_type == "service":
                raise WBTokenValidationError(
                    "WB_SERVICE_AUTH_REJECTED",
                    (
                        "Wildberries отклонил связку сервисного токена и "
                        "X-Client-Secret. Создайте токен именно для WB Insight."
                    ),
                )
            raise WBTokenValidationError(
                "WB_TOKEN_REJECTED",
                "Wildberries отклонил токен для этого способа подключения.",
            )

        if response.status_code == 429:
            raise WBTokenValidationError(
                "WB_TOKEN_VALIDATION_RATE_LIMITED",
                "Wildberries временно ограничил проверку токена. Повторите позже.",
                status_code=503,
            )

        if 500 <= response.status_code <= 599:
            raise WBTokenValidationError(
                "WB_TOKEN_VALIDATION_UNAVAILABLE",
                "Wildberries временно недоступен для проверки токена.",
                status_code=503,
            )

        raise WBTokenValidationError(
            "WB_TOKEN_REJECTED",
            "Wildberries не подтвердил подключение по этому токену.",
        )
    finally:
        if owns_client:
            await client.aclose()
