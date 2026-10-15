from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any, Awaitable, Callable
from urllib.parse import parse_qs
from uuid import UUID, uuid4

from core.operation_context import (
    OperationContext,
    bind_operation_context,
    get_actor_user_id,
    reset_operation_context,
)
from services.operation_context_snapshot_service import build_operation_user_snapshot
from services.operation_log_service import persist_operation_event, sanitize_operation_data


_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{8,64}$")
_EXCLUDED_PREFIXES = (
    "/health",
    "/static",
    "/uploads",
    "/docs",
    "/redoc",
    "/openapi.json",
)
_CAPTURE_LIMIT = 128 * 1024
_SAFE_REQUEST_HEADERS = {
    "accept",
    "accept-language",
    "content-length",
    "content-type",
    "origin",
    "referer",
    "user-agent",
    "x-forwarded-for",
    "x-real-ip",
    "x-request-id",
}
_SAFE_RESPONSE_HEADERS = {
    "content-length",
    "content-type",
    "location",
    "retry-after",
}


def _header_map(scope: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw_name, raw_value in scope.get("headers", []):
        name = raw_name.decode("latin-1").lower()
        value = raw_value.decode("latin-1")
        result[name] = value
    return result


def _request_id(headers: dict[str, str]) -> str:
    incoming = str(headers.get("x-request-id") or "").strip()
    return incoming if _REQUEST_ID_RE.fullmatch(incoming) else uuid4().hex


def _operation_id(headers: dict[str, str]) -> UUID:
    raw_value = str(headers.get("x-operation-id") or "").strip()
    try:
        return UUID(raw_value) if raw_value else uuid4()
    except ValueError:
        return uuid4()


def _replace_scope_header(scope: dict[str, Any], name: str, value: str) -> None:
    encoded_name = name.lower().encode("latin-1")
    headers = [
        (key, item)
        for key, item in scope.get("headers", [])
        if key.lower() != encoded_name
    ]
    headers.append((encoded_name, value.encode("latin-1")))
    scope["headers"] = headers


def _with_response_header(
    headers: list[tuple[bytes, bytes]],
    name: str,
    value: str,
) -> list[tuple[bytes, bytes]]:
    encoded_name = name.lower().encode("latin-1")
    result = [(key, item) for key, item in headers if key.lower() != encoded_name]
    result.append((encoded_name, value.encode("latin-1")))
    return result


def _safe_headers(headers: dict[str, str], allowed: set[str]) -> dict[str, str]:
    return {
        name: value
        for name, value in headers.items()
        if name in allowed
    }


def _response_header_map(headers: list[tuple[bytes, bytes]]) -> dict[str, str]:
    return {
        name.decode("latin-1").lower(): value.decode("latin-1")
        for name, value in headers
    }


def _decode_body(
    captured: bytes,
    *,
    total_bytes: int,
    digest: str,
    content_type: str | None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "bytes": total_bytes,
        "captured_bytes": len(captured),
        "sha256": digest,
        "truncated": total_bytes > len(captured),
        "content_type": content_type,
    }
    if total_bytes == 0:
        metadata["data"] = None
        return metadata

    lowered = str(content_type or "").lower()
    if "multipart/form-data" in lowered:
        metadata["data"] = "[ТЕЛО MULTIPART НЕ СОХРАНЯЕТСЯ]"
        return metadata

    text = captured.decode("utf-8", errors="replace")
    if "application/json" in lowered or "+json" in lowered:
        try:
            metadata["data"] = sanitize_operation_data(json.loads(text))
        except (TypeError, ValueError):
            metadata["data"] = text
        return metadata

    if "application/x-www-form-urlencoded" in lowered:
        parsed = {
            key: values[0] if len(values) == 1 else values
            for key, values in parse_qs(text, keep_blank_values=True).items()
        }
        metadata["data"] = sanitize_operation_data(parsed)
        return metadata

    if lowered.startswith("text/"):
        metadata["data"] = text
        return metadata

    metadata["data"] = "[ДВОИЧНОЕ ТЕЛО НЕ СОХРАНЯЕТСЯ]"
    return metadata


def _actor_from_scope(scope: dict[str, Any]) -> UUID | None:
    context_actor = get_actor_user_id()
    if context_actor is not None:
        return context_actor

    state = scope.get("state") or {}
    user = state.get("user") if isinstance(state, dict) else None
    if not isinstance(user, dict) or not user.get("sub"):
        return None
    try:
        return UUID(str(user["sub"]))
    except (TypeError, ValueError):
        return None


def _status_payload(status_code: int) -> tuple[str, str]:
    if status_code < 400:
        return "success", "info"
    if status_code < 500:
        return "warning", "warning"
    return "failed", "error"


def _response_error_code(payload: dict[str, Any]) -> str | None:
    body = payload.get("data")
    if not isinstance(body, dict):
        return None
    error = body.get("error")
    if isinstance(error, dict) and error.get("code"):
        return str(error["code"])
    detail = body.get("detail")
    if isinstance(detail, dict) and detail.get("error_type"):
        return str(detail["error_type"])
    return None


class OperationTraceMiddleware:
    """Сохраняет сквозную трассировку входа, выхода и контекста HTTP-операции."""

    def __init__(self, app: Callable[..., Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "/")
        if path.startswith(_EXCLUDED_PREFIXES):
            await self.app(scope, receive, send)
            return

        headers = _header_map(scope)
        request_id = _request_id(headers)
        operation_id = _operation_id(headers)
        _replace_scope_header(scope, "x-request-id", request_id)
        _replace_scope_header(scope, "x-operation-id", str(operation_id))
        scope.setdefault("state", {})["request_id"] = request_id
        scope["state"]["operation_id"] = operation_id

        token = bind_operation_context(
            OperationContext(operation_id=operation_id, request_id=request_id)
        )
        started = time.perf_counter()
        request_buffer = bytearray()
        response_buffer = bytearray()
        request_total = 0
        response_total = 0
        request_digest = hashlib.sha256()
        response_digest = hashlib.sha256()
        response_status = 500
        response_headers: list[tuple[bytes, bytes]] = []

        await persist_operation_event(
            operation_id=operation_id,
            domain="http",
            operation="request",
            step="request_received",
            status="started",
            request_id=request_id,
            message=f"Получен HTTP-запрос {scope.get('method', 'GET')} {path}",
            input_data={
                "method": scope.get("method"),
                "path": path,
                "query": {
                    key: values[0] if len(values) == 1 else values
                    for key, values in parse_qs(
                        bytes(scope.get("query_string") or b"").decode("utf-8", errors="replace"),
                        keep_blank_values=True,
                    ).items()
                },
                "headers": _safe_headers(_header_map(scope), _SAFE_REQUEST_HEADERS),
                "client": {
                    "host": scope.get("client", [None])[0] if scope.get("client") else None,
                    "port": scope.get("client", [None, None])[1] if scope.get("client") else None,
                },
            },
        )

        async def traced_receive():
            nonlocal request_total
            message = await receive()
            if message.get("type") != "http.request":
                return message
            body = bytes(message.get("body") or b"")
            request_total += len(body)
            request_digest.update(body)
            remaining = max(0, _CAPTURE_LIMIT - len(request_buffer))
            if remaining:
                request_buffer.extend(body[:remaining])
            return message

        async def traced_send(message):
            nonlocal response_status, response_headers, response_total
            message_type = message.get("type")
            if message_type == "http.response.start":
                response_status = int(message.get("status") or 500)
                current_headers = list(message.get("headers") or [])
                current_headers = _with_response_header(
                    current_headers,
                    "x-request-id",
                    request_id,
                )
                current_headers = _with_response_header(
                    current_headers,
                    "x-operation-id",
                    str(operation_id),
                )
                response_headers = current_headers
                message = {**message, "headers": current_headers}
            elif message_type == "http.response.body":
                body = bytes(message.get("body") or b"")
                response_total += len(body)
                response_digest.update(body)
                remaining = max(0, _CAPTURE_LIMIT - len(response_buffer))
                if remaining:
                    response_buffer.extend(body[:remaining])
            await send(message)

        caught: Exception | None = None
        try:
            await self.app(scope, traced_receive, traced_send)
        except Exception as exc:
            caught = exc
            raise
        finally:
            actor_user_id = _actor_from_scope(scope)
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            request_headers = _header_map(scope)
            response_header_values = _response_header_map(response_headers)
            request_payload = _decode_body(
                bytes(request_buffer),
                total_bytes=request_total,
                digest=request_digest.hexdigest(),
                content_type=request_headers.get("content-type"),
            )
            response_payload = _decode_body(
                bytes(response_buffer),
                total_bytes=response_total,
                digest=response_digest.hexdigest(),
                content_type=response_header_values.get("content-type"),
            )
            user_snapshot = (
                await build_operation_user_snapshot(actor_user_id)
                if actor_user_id is not None
                else None
            )
            status_value, severity = _status_payload(response_status)
            if caught is not None:
                status_value = "failed"
                severity = "error"

            route = scope.get("route")
            route_path = getattr(route, "path", None)
            await persist_operation_event(
                operation_id=operation_id,
                domain="http",
                operation="request",
                step="request_failed" if caught is not None else "request_completed",
                status=status_value,
                severity=severity,
                user_id=actor_user_id,
                actor_user_id=actor_user_id,
                request_id=request_id,
                http_status=response_status,
                duration_ms=duration_ms,
                error_code=(
                    type(caught).__name__
                    if caught is not None
                    else _response_error_code(response_payload)
                ),
                message=(
                    f"HTTP-запрос завершился исключением: {type(caught).__name__}"
                    if caught is not None
                    else f"HTTP-запрос завершён со статусом {response_status}"
                ),
                input_data={
                    "method": scope.get("method"),
                    "path": path,
                    "route": route_path,
                    "path_params": scope.get("path_params") or {},
                    "query": {
                        key: values[0] if len(values) == 1 else values
                        for key, values in parse_qs(
                            bytes(scope.get("query_string") or b"").decode("utf-8", errors="replace"),
                            keep_blank_values=True,
                        ).items()
                    },
                    "headers": _safe_headers(request_headers, _SAFE_REQUEST_HEADERS),
                    "body": request_payload,
                    "actor_snapshot": user_snapshot,
                },
                output_data={
                    "status_code": response_status,
                    "headers": _safe_headers(response_header_values, _SAFE_RESPONSE_HEADERS),
                    "body": response_payload,
                },
                metrics={
                    "request_bytes": request_total,
                    "response_bytes": response_total,
                    "duration_ms": duration_ms,
                },
            )
            reset_operation_context(token)
