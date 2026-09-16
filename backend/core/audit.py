import json
import re
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from core.logger import setup_logger
from services.audit_service import persist_audit_event


audit_logger = setup_logger("security.audit", "security_audit.log")
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_EXCLUDED_PREFIXES = ("/health", "/static", "/uploads", "/docs", "/redoc", "/openapi.json")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,64}$")


def should_audit_request(method: str, path: str) -> bool:
    method = method.upper()
    if path.startswith(_EXCLUDED_PREFIXES):
        return False
    if method in _MUTATING_METHODS:
        return True
    # Administrative reads expose security, user, payment and incident state.
    return method in {"GET", "HEAD"} and path.startswith("/control-panel/")


def _resource_verb(method: str) -> str:
    return {
        "GET": "read",
        "HEAD": "read",
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }.get(method.upper(), method.lower())


def classify_audit_action(method: str, route_template: str | None, path: str) -> str:
    method = method.upper()
    route = route_template or path

    auth_actions = {
        "/auth/login": "auth.login",
        "/auth/logout": "auth.logout",
        "/auth/refresh": "auth.refresh",
    }
    if route in auth_actions:
        return auth_actions[route]
    if route.startswith("/auth/password-reset"):
        return "auth.password_reset"
    if route.startswith("/account"):
        return f"account.{_resource_verb(method)}"

    if route.startswith("/control-panel/audit"):
        return "admin.audit.read"
    if route.startswith("/control-panel/users"):
        return f"admin.user.{_resource_verb(method)}"
    if route.startswith("/control-panel/roles"):
        if method == "POST":
            return "admin.role.assign"
        if method == "DELETE":
            return "admin.role.remove"
        return "admin.role.read"
    if route.startswith("/control-panel/tariffs"):
        resource = "tariff_limit" if "limit" in route else "tariff"
        return f"admin.{resource}.{_resource_verb(method)}"
    if route.startswith("/control-panel/payments/providers"):
        return f"admin.payment_provider.{_resource_verb(method)}"
    if route.startswith("/control-panel/payments"):
        return "admin.payment.read" if method in {"GET", "HEAD"} else f"admin.payment.{_resource_verb(method)}"
    if route.startswith("/control-panel/operations"):
        return "admin.operations.read" if method in {"GET", "HEAD"} else f"admin.operations.{_resource_verb(method)}"

    if route.startswith("/billing"):
        if "confirm" in route:
            return "billing.payment.confirm"
        if "callback" in route:
            return "billing.provider.callback"
        if method == "POST":
            return "billing.payment.create_or_update"
        return "billing.payment.read"

    if route.startswith("/dashboard") and ("token" in route or "credential" in route):
        return f"wb_credential.{_resource_verb(method)}"
    if "sync" in route:
        return f"sync.{_resource_verb(method)}"
    if any(fragment in route for fragment in ("expense", "cost-price", "cost_price", "revenue-plan", "revenue_plan")):
        return f"financial_input.{_resource_verb(method)}"
    if "subscription" in route:
        return f"subscription.{_resource_verb(method)}"

    normalized = re.sub(r"\{[^}]+\}", "item", route).strip("/")
    normalized = re.sub(r"[^a-zA-Z0-9]+", ".", normalized).strip(".").lower() or "root"
    return f"http.{method.lower()}.{normalized}"[:128]


def infer_audit_target(route_template: str | None, path_params: dict | None) -> tuple[str | None, str | None]:
    route = route_template or ""
    params = path_params or {}

    if route.startswith("/control-panel/payments/providers") and params.get("provider"):
        provider = str(params.get("provider"))
        mode = str(params.get("mode") or "")
        return "payment_provider", f"{provider}:{mode}".rstrip(":")

    target_keys = (
        ("user_id", "user"),
        ("payment_id", "payment"),
        ("tariff_id", "tariff"),
        ("subscription_id", "subscription"),
        ("token_id", "wb_credential"),
        ("credential_id", "wb_credential"),
        ("job_id", "sync_job"),
        ("event_id", "audit_event"),
    )
    for key, target_type in target_keys:
        if params.get(key) is not None:
            return target_type, str(params[key])

    if params.get("id") is not None:
        if "/users" in route or "edit-user" in route:
            target_type = "user"
        elif "/tariffs" in route:
            target_type = "tariff"
        elif "/payments" in route:
            target_type = "payment"
        else:
            target_type = "resource"
        return target_type, str(params["id"])
    return None, None


def audit_result_for_status(status_code: int) -> str:
    if status_code < 400:
        return "success"
    if status_code in {401, 403}:
        return "denied"
    return "failed"


def _request_id(request: Request) -> str:
    incoming = (request.headers.get("x-request-id") or "").strip()
    if _REQUEST_ID_RE.fullmatch(incoming):
        return incoming
    return uuid4().hex


def _actor_context(request: Request) -> tuple[str | None, list[str] | None]:
    state_user_id = getattr(request.state, "user_id", None)
    user = getattr(request.state, "user", None)
    actor_id = state_user_id
    if actor_id is None and isinstance(user, dict):
        actor_id = user.get("sub")
    roles = getattr(request.state, "roles", None)
    if roles is None and isinstance(user, dict) and isinstance(user.get("roles"), list):
        roles = user.get("roles")
    return (str(actor_id) if actor_id else None, list(roles) if roles else None)


def _source_for_path(path: str) -> str:
    if path.startswith("/control-panel"):
        return "admin"
    if path.startswith("/account/support"):
        return "support"
    if path.startswith("/billing"):
        return "web"
    return "api"


async def _persist_request_audit(request: Request, status_code: int, request_id: str) -> None:
    route = request.scope.get("route")
    route_template = getattr(route, "path", None)
    actor_id, roles = _actor_context(request)
    target_type, target_id = infer_audit_target(route_template, request.path_params)
    action = str(getattr(request.state, "audit_action", "") or "").strip() or classify_audit_action(
        request.method,
        route_template,
        request.url.path,
    )
    result = audit_result_for_status(status_code)
    error_code = getattr(request.state, "audit_error_code", None)
    if not error_code and result != "success":
        error_code = f"http_{status_code}"

    metadata = {
        "route": route_template or request.url.path,
        "status_code": status_code,
    }
    extra_metadata = getattr(request.state, "audit_metadata", None)
    if isinstance(extra_metadata, dict):
        metadata.update(extra_metadata)

    event = {
        "request_id": request_id,
        "actor_id": actor_id,
        "action": action,
        "target_type": target_type,
        "target_id": target_id,
        "result": result,
        "status_code": status_code,
        "method": request.method.upper(),
        "path": request.url.path,
    }
    audit_logger.info(json.dumps(event, ensure_ascii=False, separators=(",", ":")))

    await persist_audit_event(
        actor_user_id=actor_id,
        actor_roles=roles,
        action=action,
        target_type=target_type,
        target_id=target_id,
        result=result,
        error_code=str(error_code) if error_code else None,
        request_id=request_id,
        source=_source_for_path(request.url.path),
        method=request.method,
        path=request.url.path,
        client_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        metadata=metadata,
    )


class AuditMiddleware(BaseHTTPMiddleware):
    """Persist a correlation-friendly audit trail for meaningful HTTP actions."""

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = _request_id(request)
        request.state.request_id = request_id
        should_audit = should_audit_request(request.method, request.url.path)

        try:
            response = await call_next(request)
        except Exception:
            if should_audit:
                await _persist_request_audit(request, 500, request_id)
            raise

        response.headers["X-Request-ID"] = request_id
        if should_audit:
            await _persist_request_audit(request, response.status_code, request_id)
        return response
