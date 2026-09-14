from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from settings import config
from utils.responce_helps import response_error


class SessionSecurityMiddleware(BaseHTTPMiddleware):
    """Compatibility guard while legacy auth routes are being retired."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path == "/auth/refresh" and request.method.upper() == "GET":
            return JSONResponse(
                status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
                content=response_error(
                    code="METHOD_NOT_ALLOWED",
                    message="Используйте POST /auth/refresh",
                ),
            )

        response = await call_next(request)

        if request.url.path == "/auth/login" and request.method.upper() == "POST":
            self._normalize_refresh_cookie(response)

        return response

    @staticmethod
    def _normalize_refresh_cookie(response: Response) -> None:
        cookie_name = config.REFRESH_COOKIE_NAME
        prefix = f"{cookie_name}="
        refresh_value = None
        retained_headers = []

        for key, value in response.raw_headers:
            if key.lower() == b"set-cookie":
                decoded = value.decode("latin-1")
                if decoded.startswith(prefix):
                    refresh_value = decoded.split(";", 1)[0].split("=", 1)[1]
                    continue
            retained_headers.append((key, value))

        if refresh_value is None:
            return

        response.raw_headers = retained_headers
        response.set_cookie(
            key=cookie_name,
            value=refresh_value,
            httponly=True,
            secure=config.COOKIE_SECURE,
            samesite=config.COOKIE_SAMESITE,
            max_age=config.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
            path="/auth/refresh",
            domain=config.COOKIE_DOMAIN,
        )
