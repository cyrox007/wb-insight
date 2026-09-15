import json
from datetime import datetime, timezone

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from core.logger import setup_logger


audit_logger = setup_logger("security.audit", "security_audit.log")

_AUDITED_PREFIXES = (
    "/control-panel",
    "/billing",
    "/account",
    "/dashboard/profile/token",
    "/dashboard/tokens",
    "/auth/logout",
    "/auth/refresh",
    "/auth/password-reset",
)
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class AuditMiddleware(BaseHTTPMiddleware):
    """Record security-sensitive mutations without logging request bodies."""

    async def dispatch(self, request: Request, call_next) -> Response:
        should_audit = (
            request.method.upper() in _MUTATING_METHODS
            and request.url.path.startswith(_AUDITED_PREFIXES)
        )

        try:
            response = await call_next(request)
        except Exception:
            if should_audit:
                self._write_event(request, 500)
            raise

        if should_audit:
            self._write_event(request, response.status_code)
        return response

    @staticmethod
    def _write_event(request: Request, status_code: int) -> None:
        user = getattr(request.state, "user", None)
        actor_id = user.get("sub") if isinstance(user, dict) else None
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor_id": actor_id,
            "method": request.method.upper(),
            "path": request.url.path,
            "status_code": status_code,
        }
        audit_logger.info(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
