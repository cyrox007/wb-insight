"""Защита публичного контура аутентификации от перебора и enumeration."""

from __future__ import annotations

import os
from typing import Awaitable, Callable

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from core.logger import setup_logger
from services.auth_rate_limit_service import (
    AuthRateLimitUnavailable,
    RateLimitDecision,
    RateLimitRule,
    check_auth_rate_limit,
)
from services.user_identity import (
    normalize_email,
    normalize_inn,
    normalize_phone,
)


logger = setup_logger(__name__)


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} должен быть положительным целым числом") from exc
    if value <= 0:
        raise RuntimeError(f"{name} должен быть положительным целым числом")
    return value


_LOGIN_WINDOW = _positive_int("AUTH_LOGIN_RATE_WINDOW_SECONDS", 300)
_LOGIN_IP_RULE = RateLimitRule(
    limit=_positive_int("AUTH_LOGIN_RATE_IP_LIMIT", 30),
    window_seconds=_LOGIN_WINDOW,
)
_LOGIN_IDENTITY_RULE = RateLimitRule(
    limit=_positive_int("AUTH_LOGIN_RATE_IDENTITY_LIMIT", 8),
    window_seconds=_LOGIN_WINDOW,
)
_CHECK_WINDOW = _positive_int("AUTH_CHECK_RATE_WINDOW_SECONDS", 300)
_CHECK_IP_RULE = RateLimitRule(
    limit=_positive_int("AUTH_CHECK_RATE_IP_LIMIT", 30),
    window_seconds=_CHECK_WINDOW,
)
_CHECK_IDENTITY_RULE = RateLimitRule(
    limit=_positive_int("AUTH_CHECK_RATE_IDENTITY_LIMIT", 10),
    window_seconds=_CHECK_WINDOW,
)
_REGISTRATION_WINDOW = _positive_int("AUTH_REGISTRATION_RATE_WINDOW_SECONDS", 3600)
_REGISTRATION_IP_RULE = RateLimitRule(
    limit=_positive_int("AUTH_REGISTRATION_RATE_IP_LIMIT", 10),
    window_seconds=_REGISTRATION_WINDOW,
)
_REGISTRATION_IDENTITY_RULE = RateLimitRule(
    limit=_positive_int("AUTH_REGISTRATION_RATE_IDENTITY_LIMIT", 4),
    window_seconds=_REGISTRATION_WINDOW,
)

_CHECK_ENDPOINTS = {
    "/auth/check-email": ("email", normalize_email, "EMAIL_INVALID", "Укажите корректный email"),
    "/auth/check-phone": (
        "phone",
        normalize_phone,
        "PHONE_INVALID",
        "Укажите корректный номер телефона",
    ),
    "/auth/check-inn": (
        "inn",
        normalize_inn,
        "INN_INVALID",
        "ИНН должен содержать 10 или 12 цифр",
    ),
}


def _payload_response(
    *,
    http_status: int,
    payload_status: str,
    code: str | None = None,
    message: str | None = None,
    **extra,
) -> JSONResponse:
    payload = {"status": payload_status}
    if code:
        payload["code"] = code
    if message:
        payload["message"] = message
    payload.update(extra)
    return JSONResponse(status_code=http_status, content=payload)


def _rate_limited(decision: RateLimitDecision) -> JSONResponse:
    retry_after = max(int(decision.retry_after_seconds), 1)
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        headers={"Retry-After": str(retry_after)},
        content={
            "status": "error",
            "code": "AUTH_RATE_LIMITED",
            "message": "Слишком много попыток. Повторите позже.",
            "retry_after_seconds": retry_after,
        },
    )


def _limiter_unavailable() -> JSONResponse:
    return _payload_response(
        http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
        payload_status="error",
        code="AUTH_RATE_LIMIT_UNAVAILABLE",
        message="Сервис защиты авторизации временно недоступен. Повторите позже.",
    )


async def _json_object(request: Request) -> dict:
    try:
        payload = await request.json()
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


async def _check_limit(
    request: Request,
    *,
    action: str,
    ip_rule: RateLimitRule,
    identity: str | None = None,
    identity_rule: RateLimitRule | None = None,
) -> JSONResponse | None:
    try:
        decision = await check_auth_rate_limit(
            request,
            action=action,
            ip_rule=ip_rule,
            identity=identity,
            identity_rule=identity_rule,
        )
    except AuthRateLimitUnavailable:
        return _limiter_unavailable()
    if decision.allowed:
        return None
    return _rate_limited(decision)


async def _neutral_check_response(request: Request) -> JSONResponse:
    field, normalizer, error_code, error_message = _CHECK_ENDPOINTS[request.url.path]
    payload = await _json_object(request)
    normalized = normalizer(payload.get(field))
    if normalized is None:
        return _payload_response(
            http_status=status.HTTP_400_BAD_REQUEST,
            payload_status="error",
            code=error_code,
            message=error_message,
        )

    limited = await _check_limit(
        request,
        action=f"check-{field}",
        ip_rule=_CHECK_IP_RULE,
        identity=normalized,
        identity_rule=_CHECK_IDENTITY_RULE,
    )
    if limited is not None:
        return limited

    return _payload_response(
        http_status=status.HTTP_200_OK,
        payload_status="success",
        message="Формат данных проверен",
        checked=True,
    )


async def _login_guard(request: Request) -> JSONResponse | None:
    payload = await _json_object(request)
    email = normalize_email(payload.get("email"))
    identity = email or str(payload.get("email") or "invalid-email")
    return await _check_limit(
        request,
        action="login",
        ip_rule=_LOGIN_IP_RULE,
        identity=identity,
        identity_rule=_LOGIN_IDENTITY_RULE,
    )


async def _registration_guard(request: Request) -> JSONResponse | None:
    payload = await _json_object(request)
    registration = payload.get("registrationData")
    registration = registration if isinstance(registration, dict) else {}
    email = normalize_email(registration.get("email"))
    identity = email or str(registration.get("email") or "invalid-email")
    return await _check_limit(
        request,
        action="registration",
        ip_rule=_REGISTRATION_IP_RULE,
        identity=identity,
        identity_rule=_REGISTRATION_IDENTITY_RULE,
    )


class PublicAuthSecurityMiddleware(BaseHTTPMiddleware):
    """Ограничивает brute force и не позволяет публичным preflight-проверкам раскрывать аккаунты."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method != "POST":
            return await call_next(request)

        path = request.url.path
        if path in _CHECK_ENDPOINTS:
            return await _neutral_check_response(request)

        guard = None
        if path == "/auth/login":
            guard = await _login_guard(request)
        elif path == "/auth/registration":
            guard = await _registration_guard(request)

        if guard is not None:
            return guard
        return await call_next(request)
