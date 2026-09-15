from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

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

        # Cookie attributes are owned exclusively by core.session_cookie.
        # Do not rewrite Set-Cookie headers here: doing so can accidentally
        # narrow Path/Domain and break logout/session recovery symmetry.
        return await call_next(request)
