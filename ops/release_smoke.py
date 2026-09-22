#!/usr/bin/env python3
"""WB Insight production-like release smoke runner.

The runner intentionally never prints passwords, access tokens, refresh cookies,
mail verification/reset tokens or marketplace credentials. Disposable registration
can exercise the real mail path through a provider-neutral external token hook.
Optional WB, billing and durable-audit phases are enabled only when requested.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
import json
import os
import shlex
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import UUID, uuid4


class SmokeFailure(RuntimeError):
    pass


class SmokeClient:
    def __init__(self, base_url: str):
        # Production-like smoke exercises the same public nginx contract as the
        # browser. Nginx exposes backend routes under /api while proxying them to
        # the FastAPI root, so callers may pass either the public origin or its
        # explicit /api root and requests are normalized to /api exactly once.
        self.base_url = _public_api_base(base_url)
        self.cookies = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cookies))
        self.access_token: str | None = None

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict | None = None,
        auth: bool = False,
        headers: dict[str, str] | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> dict:
        url = f"{self.base_url}{path}"
        request_headers = {"Accept": "application/json", **(headers or {})}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            request_headers["Content-Type"] = "application/json"
        if auth:
            if not self.access_token:
                raise SmokeFailure(f"{method} {path}: access token is not initialized")
            request_headers["Authorization"] = f"Bearer {self.access_token}"

        request = Request(url, data=data, headers=request_headers, method=method)
        status = 0
        raw = b""
        try:
            with self.opener.open(request, timeout=30) as response:
                status = response.status
                raw = response.read()
        except HTTPError as exc:
            status = exc.code
            raw = exc.read()
        except URLError as exc:
            raise SmokeFailure(f"{method} {path}: endpoint unavailable") from exc

        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SmokeFailure(f"{method} {path}: response is not JSON (HTTP {status})") from exc

        if status not in expected:
            error_code = payload.get("error", {}).get("code") if isinstance(payload, dict) else None
            suffix = f", code={error_code}" if error_code else ""
            raise SmokeFailure(f"{method} {path}: unexpected HTTP {status}{suffix}")
        return payload


def _required_consents(client: SmokeClient, context: str) -> list[dict]:
    payload = client.request("GET", f"/legal/requirements/{context}")
    documents = payload.get("documents") or []
    if not documents:
        raise SmokeFailure(f"legal context {context}: no required documents returned")
    return [
        {
            "code": document["code"],
            "version": document["version"],
            "sha256": document["sha256"],
            "accepted": True,
        }
        for document in documents
    ]


def _project_version() -> str | None:
    version_path = Path(__file__).resolve().parents[1] / "VERSION"
    if not version_path.exists():
        return None
    return version_path.read_text(encoding="utf-8").strip() or None


def _project_commit() -> str | None:
    project = Path(__file__).resolve().parents[1]
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    commit = completed.stdout.strip().lower()
    if completed.returncode != 0 or len(commit) != 40 or any(
        char not in "0123456789abcdef" for char in commit
    ):
        return None
    return commit


def _env_flag(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _safe_base_origin(value: str) -> str:
    parsed = urlparse(value.strip())
    try:
        parsed_port = parsed.port
    except ValueError as exc:
        raise SmokeFailure("SMOKE_BASE_URL contains an invalid port") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SmokeFailure("SMOKE_BASE_URL must be an http(s) origin or public /api root")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise SmokeFailure("SMOKE_BASE_URL must not contain credentials, query or fragment")
    normalized_path = parsed.path.rstrip("/")
    if normalized_path not in {"", "/api"}:
        raise SmokeFailure("SMOKE_BASE_URL path must be empty or /api")
    port = f":{parsed_port}" if parsed_port else ""
    return f"{parsed.scheme}://{parsed.hostname}{port}"


def _public_api_base(value: str) -> str:
    """Return the public API root while keeping evidence bound to the bare origin."""
    return f"{_safe_base_origin(value)}/api"


def _write_evidence(
    path: Path,
    *,
    args: argparse.Namespace,
    checks: dict[str, bool],
    mail_gateway: dict | None = None,
) -> None:
    report = {
        "schema_version": 1,
        "kind": "release_smoke",
        "status": "pass",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": args.expected_version,
        "commit": args.commit.lower(),
        "environment": args.environment,
        "base_origin": _safe_base_origin(args.base_url),
        "checks": checks,
    }
    if mail_gateway is not None:
        report["mail_gateway"] = mail_gateway
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _disposable_email(template: str | None, suffix: UUID) -> str:
    """Build a unique smoke address without guessing a production mail domain."""
    if template is None:
        template = "release-smoke+{uuid}@smoke.invalid"
    if "{uuid}" not in template:
        raise SmokeFailure("SMOKE_DISPOSABLE_EMAIL_TEMPLATE must contain {uuid}")
    email = template.replace("{uuid}", suffix.hex).strip().lower()
    if email.count("@") != 1 or any(char.isspace() for char in email) or len(email) > 254:
        raise SmokeFailure("SMOKE_DISPOSABLE_EMAIL_TEMPLATE produced an invalid email")
    return email


def _extract_mail_token(value: str) -> str:
    """Accept a raw token or a URL whose token is only in the fragment."""
    candidate = value.strip()
    if not candidate or "\n" in candidate or "\r" in candidate:
        raise SmokeFailure("mail token hook returned an invalid response")

    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise SmokeFailure("mail token hook returned an invalid URL")
        fragment = parse_qs(parsed.fragment, keep_blank_values=False)
        token_values = fragment.get("token") or []
        if len(token_values) != 1 or not token_values[0]:
            raise SmokeFailure("mail hook URL must keep token in #token= fragment")
        candidate = token_values[0]

    if len(candidate) < 16 or len(candidate) > 1024 or any(char.isspace() for char in candidate):
        raise SmokeFailure("mail token hook returned an invalid token")
    return candidate


def _mail_token_from_hook(
    command: str,
    *,
    kind: str,
    email: str,
    timeout_seconds: int,
) -> str:
    """Run a provider-specific inbox helper without exposing its secret output.

    Contract: command receives KIND and EMAIL as final argv values (and also through
    WB_SMOKE_MAIL_KIND/WB_SMOKE_EMAIL), waits for the matching message, then prints
    exactly one raw token or verification/reset URL. stdout/stderr are never echoed.
    """
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        raise SmokeFailure("SMOKE_MAIL_TOKEN_COMMAND is invalid") from exc
    if not argv:
        raise SmokeFailure("SMOKE_MAIL_TOKEN_COMMAND is empty")

    env = os.environ.copy()
    env["WB_SMOKE_MAIL_KIND"] = kind
    env["WB_SMOKE_EMAIL"] = email
    try:
        completed = subprocess.run(
            [*argv, kind, email],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise SmokeFailure(f"mail token hook timed out for {kind}") from exc
    except OSError as exc:
        raise SmokeFailure("mail token hook could not be started") from exc

    if completed.returncode != 0:
        # Never surface hook stderr: provider clients often include message bodies
        # or credentials in diagnostic output.
        raise SmokeFailure(f"mail token hook failed for {kind} (exit {completed.returncode})")
    return _extract_mail_token(completed.stdout)


def _require_real_disposable_mail(
    email: str,
    *,
    mail_token_command: str | None,
) -> None:
    domain = email.rsplit("@", 1)[-1]
    if domain.endswith(".invalid"):
        raise SmokeFailure(
            "real mail smoke requires SMOKE_DISPOSABLE_EMAIL_TEMPLATE with a deliverable domain"
        )
    if not mail_token_command:
        raise SmokeFailure("real mail smoke requires SMOKE_MAIL_TOKEN_COMMAND")


def run_public_smoke(client: SmokeClient, expected_version: str | None) -> None:
    live = client.request("GET", "/health/live")
    if live.get("status") != "ok":
        raise SmokeFailure("liveness status is not ok")
    if expected_version and live.get("version") != expected_version:
        raise SmokeFailure(
            f"deployed version mismatch: expected {expected_version}, got {live.get('version')}"
        )

    ready = client.request("GET", "/health/ready")
    if ready.get("status") != "ok":
        raise SmokeFailure("readiness status is not ok")

    for context in ("registration", "registration_legal", "billing", "marketplace_credential"):
        _required_consents(client, context)

    print("[ok] public health/readiness and legal document registry")


def _login_disposable(client: SmokeClient, email: str, password: str) -> str:
    login = client.request(
        "POST",
        "/auth/login",
        body={"email": email, "password": password},
    )
    if login.get("status") != "success" or not login.get("access_token"):
        raise SmokeFailure("disposable account login did not return access token")
    client.access_token = login["access_token"]
    user_id = login.get("user", {}).get("id")
    if not user_id:
        raise SmokeFailure("disposable account login did not return user identity")
    return str(user_id)


def run_disposable_registration_smoke(
    base_url: str,
    *,
    email_template: str | None = None,
    mail_token_command: str | None = None,
    mail_token_timeout: int = 180,
    require_email_verification: bool = False,
    require_password_reset: bool = False,
    mail_admin_email: str | None = None,
    mail_admin_password: str | None = None,
) -> dict[str, bool]:
    """Prove registration, real mail, demo, consent and session lifecycle."""
    client = SmokeClient(base_url)
    suffix = uuid4()
    email = _disposable_email(email_template, suffix)
    phone = f"+7{suffix.int % 10_000_000_000:010d}"
    password = f"Smoke-{suffix.hex[:12]}-A7!"

    if require_email_verification or require_password_reset:
        _require_real_disposable_mail(email, mail_token_command=mail_token_command)

    required_consents = _required_consents(client, "registration")
    expected_evidence = {
        (item["code"], item["version"], item["sha256"])
        for item in required_consents
    }

    registered = False
    deactivated = False
    verification_required = False
    try:
        registration = client.request(
            "POST",
            "/auth/registration",
            body={
                "registrationData": {
                    "email": email,
                    "phone": phone,
                    "full_name": "Release Smoke User",
                    "password": password,
                    "entity_type": "individual",
                    "timezone": "Europe/Berlin",
                    "legal_consents": required_consents,
                    "newsletter_subscription": False,
                }
            },
        )
        if registration.get("status") != "success":
            raise SmokeFailure("disposable registration did not succeed")
        registered = True

        verification_required = registration.get("email_verification_required") is True
        if require_email_verification and not verification_required:
            raise SmokeFailure("beta smoke requires email verification but deployment did not require it")

        if verification_required:
            _require_real_disposable_mail(email, mail_token_command=mail_token_command)
            verification_token = _mail_token_from_hook(
                mail_token_command or "",
                kind="email_verification",
                email=email,
                timeout_seconds=mail_token_timeout,
            )
            verified = client.request(
                "POST",
                "/auth/email-verification/confirm",
                body={"token": verification_token},
            )
            if verified.get("status") != "success" or verified.get("email", "").lower() != email:
                raise SmokeFailure("email verification did not confirm the disposable identity")
            print("[ok] disposable registration email delivered and verified")

        user_id = _login_disposable(client, email, password)
        if verification_required:
            # Session identity must reflect the durable verification state.
            refreshed_identity = client.request("POST", "/auth/refresh", body={})
            if refreshed_identity.get("user", {}).get("email_verified") is not True:
                raise SmokeFailure("verified disposable session did not expose email_verified=true")
            client.access_token = refreshed_identity.get("access_token")

        profile = client.request("GET", "/dashboard/profile/", auth=True)
        subscription = profile.get("subscription") or {}
        if subscription.get("status") != "demo" or subscription.get("is_active") is not True:
            raise SmokeFailure("verified registration did not create an active demo subscription")

        evidence_payload = client.request("GET", "/legal/consents/me", auth=True)
        records = evidence_payload.get("consents") or []
        actual_evidence = {
            (
                record.get("document_code"),
                record.get("document_version"),
                record.get("document_sha256"),
            )
            for record in records
            if record.get("context") == "registration"
            and record.get("context_reference") == user_id
        }
        if not expected_evidence.issubset(actual_evidence):
            raise SmokeFailure("registration legal consent evidence was not persisted exactly")

        if require_password_reset:
            if not mail_admin_email or not mail_admin_password:
                raise SmokeFailure(
                    "password reset throttle smoke requires staff/admin mail diagnostics credentials"
                )

            reset_request = client.request(
                "POST",
                "/auth/password-reset/request",
                body={"email": email},
                expected=(202,),
            )
            if reset_request.get("status") != "success":
                raise SmokeFailure("password reset request did not enter the mail queue")

            repeated_request = client.request(
                "POST",
                "/auth/password-reset/request",
                body={"email": email},
                expected=(202,),
            )
            if repeated_request.get("status") != "success":
                raise SmokeFailure("repeated password reset request changed the public contract")
            if repeated_request.get("message") != reset_request.get("message"):
                raise SmokeFailure("password reset throttle broke the anti-enumeration response contract")

            run_password_reset_throttle_smoke(
                base_url,
                email=mail_admin_email,
                password=mail_admin_password,
                user_id=user_id,
            )

            reset_token = _mail_token_from_hook(
                mail_token_command or "",
                kind="password_reset",
                email=email,
                timeout_seconds=mail_token_timeout,
            )
            new_password = f"{password}-R1"
            stale_access_token = client.access_token
            reset = client.request(
                "POST",
                "/auth/password-reset/confirm",
                body={"token": reset_token, "new_password": new_password},
            )
            if reset.get("status") != "success":
                raise SmokeFailure("password reset confirmation did not succeed")

            if stale_access_token:
                stale_client = SmokeClient(base_url)
                stale_client.access_token = stale_access_token
                stale_access = stale_client.request(
                    "GET",
                    "/dashboard/profile/",
                    auth=True,
                    expected=(401,),
                )
                error_type = (stale_access.get("detail") or {}).get("error_type")
                if error_type != "session_revoked":
                    raise SmokeFailure("password reset did not revoke the previously issued access token")

            client.access_token = None
            restored_user_id = _login_disposable(client, email, new_password)
            if restored_user_id != user_id:
                raise SmokeFailure("password reset login restored the wrong identity")
            password = new_password
            print(
                "[ok] password reset delivered through real mail, throttle held and old session was revoked"
            )

        # Browser reload semantics for a newly registered account as well.
        client.access_token = None
        refreshed = client.request("POST", "/auth/refresh", body={})
        if refreshed.get("status") != "success" or not refreshed.get("access_token"):
            raise SmokeFailure("disposable account refresh did not restore access token")
        if refreshed.get("user", {}).get("id") != user_id:
            raise SmokeFailure("disposable account refresh restored the wrong identity")
        client.access_token = refreshed["access_token"]

        result = client.request(
            "POST",
            "/account/deactivate",
            auth=True,
            body={"reason": "release smoke cleanup"},
        )
        if result.get("status") != "success" or result.get("deactivated") is not True:
            raise SmokeFailure("disposable account cleanup did not deactivate account")
        deactivated = True
        client.access_token = None

        refresh_after = client.request("POST", "/auth/refresh", body={}, expected=(401,))
        if refresh_after.get("error", {}).get("code") not in {"INVALID_TOKEN", "SESSION_REVOKED"}:
            raise SmokeFailure("deactivated account retained a refresh session")

        login_after = client.request(
            "POST",
            "/auth/login",
            body={"email": email, "password": password},
            expected=(403,),
        )
        if login_after.get("error", {}).get("code") != "USER_INACTIVE":
            raise SmokeFailure("deactivated disposable account can still authenticate")
    finally:
        if registered and not deactivated:
            if not client.access_token:
                try:
                    cleanup_login = client.request(
                        "POST",
                        "/auth/login",
                        body={"email": email, "password": password},
                    )
                    token = cleanup_login.get("access_token")
                    if cleanup_login.get("status") == "success" and token:
                        client.access_token = token
                except SmokeFailure:
                    pass

            if client.access_token:
                try:
                    cleanup_result = client.request(
                        "POST",
                        "/account/deactivate",
                        auth=True,
                        body={"reason": "release smoke cleanup after failure"},
                    )
                    deactivated = (
                        cleanup_result.get("status") == "success"
                        and cleanup_result.get("deactivated") is True
                    )
                except SmokeFailure:
                    pass
            client.access_token = None

    mail_note = ", real email verification" if verification_required else ""
    reset_note = ", real password reset" if require_password_reset else ""
    print(
        "[ok] disposable registration"
        f"{mail_note}{reset_note}, demo subscription, consent evidence, refresh and deactivation"
    )
    return {
        "disposable_registration": True,
        "email_verification": verification_required,
        "password_reset": require_password_reset,
        "password_reset_throttle": require_password_reset,
        "password_reset_session_revoked": require_password_reset,
        "demo_activation": True,
        "legal_consent_evidence": True,
        "refresh_restore": True,
        "deactivation": True,
        "inactive_login_rejected": True,
    }


def _login_smoke_client(client: SmokeClient, email: str, password: str) -> dict:
    login = client.request(
        "POST",
        "/auth/login",
        body={"email": email, "password": password},
    )
    if login.get("status") != "success" or not login.get("access_token") or not login.get("user"):
        raise SmokeFailure("login did not return access token and user identity")
    client.access_token = login["access_token"]
    return login


def run_password_reset_throttle_smoke(
    base_url: str,
    *,
    email: str,
    password: str,
    user_id: str,
) -> None:
    """Prove two immediate public reset requests materialize one durable mail row."""
    client = SmokeClient(base_url)
    probe_error: SmokeFailure | None = None
    try:
        _login_smoke_client(client, email, password)
        payload = client.request(
            "GET",
            f"/control-panel/mail/diagnostics/password-reset/{user_id}",
            auth=True,
        )
        if payload.get("status") != "success":
            raise SmokeFailure("password reset throttle diagnostics returned an invalid envelope")
        try:
            message_count = int(payload.get("password_reset_messages"))
            resend_seconds = int(payload.get("resend_seconds"))
        except (TypeError, ValueError) as exc:
            raise SmokeFailure("password reset throttle diagnostics returned invalid counters") from exc
        if message_count != 1:
            raise SmokeFailure(
                f"password reset throttle expected one durable mail row, got {message_count}"
            )
        if resend_seconds <= 0:
            raise SmokeFailure("password reset resend throttle is not configured")
        print("[ok] password reset resend throttle and idempotent queue materialization")
    except SmokeFailure as exc:
        probe_error = exc
    finally:
        if client.access_token or any(True for _ in client.cookies):
            try:
                run_logout_smoke(client)
            except SmokeFailure as cleanup_exc:
                if probe_error is not None:
                    raise SmokeFailure(
                        f"{probe_error}; password reset throttle probe logout cleanup also failed"
                    ) from cleanup_exc
                raise

    if probe_error is not None:
        raise probe_error


def run_authenticated_smoke(client: SmokeClient, email: str, password: str) -> None:
    login = _login_smoke_client(client, email, password)
    user_id = login["user"].get("id")

    profile = client.request("GET", "/dashboard/profile/", auth=True)
    if profile.get("status") != "success" or profile.get("user", {}).get("id") != user_id:
        raise SmokeFailure("authenticated profile identity does not match login identity")

    # Browser reload semantics: access JWT is deliberately discarded. The
    # HttpOnly refresh cookie alone must restore both access JWT and user state.
    client.access_token = None
    refreshed = client.request("POST", "/auth/refresh", body={})
    if refreshed.get("status") != "success" or not refreshed.get("access_token"):
        raise SmokeFailure("refresh did not restore an access token")
    if refreshed.get("user", {}).get("id") != user_id:
        raise SmokeFailure("refresh did not restore the same user identity")
    client.access_token = refreshed["access_token"]

    dashboard = client.request("GET", "/dashboard/", auth=True)
    if dashboard.get("status") not in {"success", "error"}:
        raise SmokeFailure("dashboard returned an invalid API envelope")
    if dashboard.get("status") == "error":
        allowed = {"NO_VALID_TOKENS", "NOT_SYNCED", "SYNC_ERROR", "TOKEN_INVALID"}
        code = dashboard.get("error", {}).get("code")
        if code not in allowed:
            raise SmokeFailure(f"dashboard returned unexpected error code {code}")

    print("[ok] login, protected API, cookie-only refresh restore")


def _validate_mail_gateway_payload(
    payload: dict,
    *,
    expected_provider: str | None,
    require_email_verification: bool,
    require_password_reset: bool,
) -> None:
    if payload.get("status") != "success":
        raise SmokeFailure("mail gateway preflight returned an invalid API envelope")

    gateway = payload.get("gateway") or {}
    provider = str(gateway.get("provider") or "").strip().lower()
    if expected_provider and provider != expected_provider:
        raise SmokeFailure(
            f"mail gateway provider mismatch: expected {expected_provider}, got {provider or 'unconfigured'}"
        )
    if gateway.get("ready") is not True:
        diagnostic = str(gateway.get("diagnostic_code") or "not_ready")
        raise SmokeFailure(f"mail gateway is not ready ({diagnostic})")

    system_mail = gateway.get("system_mail") or {}
    if require_email_verification:
        verification = system_mail.get("email_verification") or {}
        if verification.get("ready") is not True:
            raise SmokeFailure("email verification mail capability is not ready")
    if require_password_reset:
        recovery = system_mail.get("password_reset") or {}
        if recovery.get("ready") is not True:
            raise SmokeFailure("password reset mail capability is not ready")


def run_mail_gateway_readiness_smoke(
    client: SmokeClient,
    *,
    expected_provider: str | None,
    require_email_verification: bool,
    require_password_reset: bool,
) -> dict:
    """Fail early on admin-visible mail misconfiguration before real-mail smoke."""
    payload = client.request(
        "GET",
        "/control-panel/mail/gateway",
        auth=True,
    )
    _validate_mail_gateway_payload(
        payload,
        expected_provider=expected_provider,
        require_email_verification=require_email_verification,
        require_password_reset=require_password_reset,
    )
    gateway = payload.get("gateway") or {}
    provider = str(gateway.get("provider") or "unknown").strip().lower()
    system_mail = gateway.get("system_mail") or {}
    evidence = {
        "provider": provider,
        "expected_provider": expected_provider,
        "source": str(gateway.get("source") or "unknown"),
        "config_source": str(gateway.get("config_source") or "unknown"),
        "email_verification_ready": bool(
            (system_mail.get("email_verification") or {}).get("ready")
        ),
        "password_reset_ready": bool(
            (system_mail.get("password_reset") or {}).get("ready")
        ),
    }
    print(f"[ok] mail gateway readiness: provider={provider}")
    return evidence


def run_mail_gateway_authenticated_preflight(
    base_url: str,
    *,
    email: str,
    password: str,
    expected_provider: str | None,
    require_email_verification: bool,
    require_password_reset: bool,
) -> dict:
    """Authenticate a staff account, validate mail readiness, and revoke that session."""
    client = SmokeClient(base_url)
    preflight_error: SmokeFailure | None = None
    evidence: dict | None = None
    try:
        _login_smoke_client(client, email, password)
        evidence = run_mail_gateway_readiness_smoke(
            client,
            expected_provider=expected_provider,
            require_email_verification=require_email_verification,
            require_password_reset=require_password_reset,
        )
    except SmokeFailure as exc:
        preflight_error = exc
    finally:
        if client.access_token or any(True for _ in client.cookies):
            try:
                run_logout_smoke(client)
            except SmokeFailure as cleanup_exc:
                if preflight_error is not None:
                    raise SmokeFailure(
                        f"{preflight_error}; mail gateway preflight logout cleanup also failed"
                    ) from cleanup_exc
                raise

    if preflight_error is not None:
        raise preflight_error
    if evidence is None:
        raise SmokeFailure("mail gateway preflight completed without evidence")
    return evidence


def run_audit_correlation_smoke(client: SmokeClient) -> None:
    """Prove a sensitive admin read becomes queryable through durable P37 audit."""
    request_id = f"release-smoke-{uuid4().hex}"
    initial = client.request(
        "GET",
        "/control-panel/audit/?limit=1",
        auth=True,
        headers={"X-Request-ID": request_id},
    )
    if initial.get("status") != "success":
        raise SmokeFailure("audit smoke could not read Control Panel audit")

    query = urlencode({"request_id": request_id, "limit": 10})
    for _ in range(10):
        payload = client.request("GET", f"/control-panel/audit/?{query}", auth=True)
        events = payload.get("events") or []
        if any(
            event.get("request_id") == request_id
            and event.get("result") == "success"
            and event.get("path", "").startswith("/control-panel/audit")
            for event in events
        ):
            print("[ok] durable audit correlation by request id")
            return
        time.sleep(0.25)
    raise SmokeFailure("durable audit event was not queryable by request id")


def run_wb_credential_smoke(client: SmokeClient, wb_token: str) -> None:
    consents = _required_consents(client, "marketplace_credential")
    created_id = None
    try:
        created = client.request(
            "POST",
            "/dashboard/tokens",
            auth=True,
            body={
                "token": wb_token,
                "label": f"release-smoke-{uuid4().hex[:8]}",
                "legal_consents": consents,
            },
        )
        if created.get("status") != "success":
            raise SmokeFailure("WB credential creation did not succeed")
        data = created.get("data") if isinstance(created.get("data"), dict) else {}
        # Cleanup endpoint accepts the internal credential UUID (`token.id`).
        # `external_account_id` identifies the seller and must never be used as
        # the delete path parameter.
        created_id = data.get("id") or created.get("id")
        if not created_id:
            raise SmokeFailure("WB credential smoke did not return internal credential id")
        print("[ok] WB credential live validation and storage")
    finally:
        if created_id:
            deleted = client.request(
                "DELETE",
                f"/dashboard/profile/token/{created_id}",
                auth=True,
            )
            if deleted.get("status") != "success":
                raise SmokeFailure("WB credential smoke cleanup failed")
            print("[ok] WB credential cleanup")


def run_billing_init_smoke(client: SmokeClient, tariff_code: str) -> None:
    consents = _required_consents(client, "billing")
    payment = client.request(
        "POST",
        "/billing/create-payment",
        auth=True,
        headers={"Idempotency-Key": f"release-smoke-{uuid4()}"},
        body={"tariff_code": tariff_code, "legal_consents": consents},
    )
    if payment.get("status") != "success" or not payment.get("payment_id"):
        raise SmokeFailure("billing init smoke did not create payment attempt")
    print(f"[ok] billing payment-init: payment_id={payment['payment_id']}")
    if payment.get("confirmation_url"):
        print("[action] complete the sandbox/production payment using the provider page, then verify confirmation and merchant back office")


def run_logout_smoke(client: SmokeClient) -> None:
    # Logout is cookie-driven and intentionally does not require an access JWT.
    # This matters when an earlier refresh assertion failed after the runner had
    # deliberately discarded its in-memory access token.
    client.request("POST", "/auth/logout", body={})
    client.access_token = None
    payload = client.request("POST", "/auth/refresh", body={}, expected=(401,))
    if payload.get("error", {}).get("code") not in {"INVALID_TOKEN", "SESSION_REVOKED"}:
        raise SmokeFailure("refresh after logout did not return the expected session error")
    print("[ok] logout clears refresh session")


def _self_test() -> None:
    suffix = UUID("12345678-1234-5678-1234-567812345678")
    assert _disposable_email("smoke+{uuid}@example.com", suffix) == (
        "smoke+12345678123456781234567812345678@example.com"
    )
    assert _extract_mail_token("abcdefghijklmnop") == "abcdefghijklmnop"
    assert _extract_mail_token(
        "https://app.example.com/verify-email#token=abcdefghijklmnop"
    ) == "abcdefghijklmnop"
    assert _safe_base_origin("https://example.com/") == "https://example.com"
    assert _safe_base_origin("https://example.com/api") == "https://example.com"
    assert _public_api_base("https://example.com") == "https://example.com/api"
    assert _public_api_base("https://example.com/api/") == "https://example.com/api"
    for invalid_base in ("https://example.com/backend", "https://example.com:bad-port"):
        try:
            _safe_base_origin(invalid_base)
        except SmokeFailure:
            pass
        else:
            raise AssertionError(f"unexpected public API base accepted: {invalid_base}")
    try:
        _extract_mail_token("https://app.example.com/verify-email?token=abcdefghijklmnop")
    except SmokeFailure:
        pass
    else:
        raise AssertionError("query-string secret unexpectedly accepted")

    _validate_mail_gateway_payload(
        {
            "status": "success",
            "gateway": {
                "provider": "rusender",
                "ready": True,
                "diagnostic_code": None,
                "system_mail": {
                    "email_verification": {"ready": True},
                    "password_reset": {"ready": True},
                },
            },
        },
        expected_provider="rusender",
        require_email_verification=True,
        require_password_reset=True,
    )
    try:
        _validate_mail_gateway_payload(
            {
                "status": "success",
                "gateway": {
                    "provider": "rusender",
                    "ready": False,
                    "diagnostic_code": "environment_fallback_invalid",
                },
            },
            expected_provider="rusender",
            require_email_verification=False,
            require_password_reset=False,
        )
    except SmokeFailure:
        pass
    else:
        raise AssertionError("not-ready mail gateway unexpectedly passed preflight")

    class _FakeGatewayClient:
        def request(self, method, path, *, auth=False, **_kwargs):
            assert method == "GET"
            assert path == "/control-panel/mail/gateway"
            assert auth is True
            return {
                "status": "success",
                "gateway": {
                    "provider": "rusender",
                    "ready": True,
                    "source": "database",
                    "config_source": "auto",
                    "system_mail": {
                        "email_verification": {"ready": True},
                        "password_reset": {"ready": True},
                    },
                },
            }

    gateway_evidence = run_mail_gateway_readiness_smoke(
        _FakeGatewayClient(),  # type: ignore[arg-type]
        expected_provider="rusender",
        require_email_verification=True,
        require_password_reset=True,
    )
    assert gateway_evidence == {
        "provider": "rusender",
        "expected_provider": "rusender",
        "source": "database",
        "config_source": "auto",
        "email_verification_ready": True,
        "password_reset_ready": True,
    }

    class _FakeLoginClient:
        access_token = None

        def request(self, method, path, *, body=None, **_kwargs):
            assert method == "POST"
            assert path == "/auth/login"
            assert body == {"email": "staff@example.com", "password": "secret"}
            return {
                "status": "success",
                "access_token": "access-token",
                "user": {"id": "user-id"},
            }

    fake_login_client = _FakeLoginClient()
    fake_login = _login_smoke_client(
        fake_login_client,  # type: ignore[arg-type]
        "staff@example.com",
        "secret",
    )
    assert fake_login_client.access_token == "access-token"
    assert fake_login["user"]["id"] == "user-id"
    print("[ok] release smoke self-test")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run WB Insight production-like release smoke")
    parser.add_argument(
        "--base-url",
        default=os.getenv("SMOKE_BASE_URL"),
        help="Public HTTPS origin or its /api root; backend requests are sent through /api",
    )
    parser.add_argument("--email", default=os.getenv("SMOKE_EMAIL"))
    parser.add_argument("--password", default=os.getenv("SMOKE_PASSWORD"))
    parser.add_argument(
        "--expected-version",
        default=os.getenv("SMOKE_EXPECTED_VERSION") or _project_version(),
    )
    parser.add_argument(
        "--commit",
        default=os.getenv("RELEASE_SHA") or _project_commit(),
        help="Exact deployed Git commit; required when writing structured evidence",
    )
    parser.add_argument(
        "--environment",
        default=os.getenv("ACCEPTANCE_ENVIRONMENT"),
        help="Production-like environment id; required when writing structured evidence",
    )
    parser.add_argument("--public-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument(
        "--skip-disposable-registration",
        action="store_true",
        default=_env_flag("SMOKE_SKIP_DISPOSABLE_REGISTRATION"),
        help="Skip disposable registration/demo/consent lifecycle verification",
    )
    parser.add_argument(
        "--disposable-email-template",
        default=os.getenv("SMOKE_DISPOSABLE_EMAIL_TEMPLATE"),
        help="Unique deliverable address template; must contain {uuid}",
    )
    parser.add_argument(
        "--mail-token-command",
        default=os.getenv("SMOKE_MAIL_TOKEN_COMMAND"),
        help="Inbox hook command; receives KIND EMAIL and prints only raw token or fragment URL",
    )
    parser.add_argument(
        "--mail-token-timeout",
        type=int,
        default=int(os.getenv("SMOKE_MAIL_TOKEN_TIMEOUT_SECONDS", "180")),
    )
    parser.add_argument(
        "--require-email-verification",
        action="store_true",
        default=_env_flag("SMOKE_REQUIRE_EMAIL_VERIFICATION"),
        help="Fail unless registration requires and completes real email verification",
    )
    parser.add_argument(
        "--require-password-reset",
        action="store_true",
        default=_env_flag("SMOKE_REQUIRE_PASSWORD_RESET"),
        help="Exercise password reset through the same real mail token hook",
    )
    parser.add_argument(
        "--mail-gateway-smoke",
        action="store_true",
        default=_env_flag("SMOKE_MAIL_GATEWAY"),
        help="Require authenticated Control Panel mail gateway readiness preflight",
    )
    parser.add_argument(
        "--expected-mail-provider",
        default=os.getenv("SMOKE_EXPECTED_MAIL_PROVIDER"),
        help="Optional expected effective provider, for example rusender",
    )
    parser.add_argument(
        "--audit-smoke",
        action="store_true",
        default=_env_flag("SMOKE_AUDIT"),
        help="Require the authenticated account to prove durable Control Panel audit correlation",
    )
    parser.add_argument("--wb-token", default=os.getenv("SMOKE_WB_TOKEN"))
    parser.add_argument("--billing-tariff", default=os.getenv("SMOKE_BILLING_TARIFF"))
    parser.add_argument(
        "--evidence-output",
        type=Path,
        default=Path(os.environ["SMOKE_EVIDENCE_OUTPUT"]) if os.getenv("SMOKE_EVIDENCE_OUTPUT") else None,
        help="Write a sanitized machine-readable pass report",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.self_test:
        _self_test()
        return 0
    if not args.base_url:
        raise SmokeFailure("SMOKE_BASE_URL or --base-url is required")
    _safe_base_origin(args.base_url)
    if args.mail_token_timeout <= 0 or args.mail_token_timeout > 1800:
        raise SmokeFailure("mail token timeout must be between 1 and 1800 seconds")
    if args.skip_disposable_registration and (
        args.require_email_verification or args.require_password_reset
    ):
        raise SmokeFailure(
            "required email verification/password reset cannot be combined with skipped disposable registration"
        )
    if args.expected_mail_provider:
        args.expected_mail_provider = str(args.expected_mail_provider).strip().lower()
        if args.expected_mail_provider not in {"smtp", "rusender"}:
            raise SmokeFailure("expected mail provider must be smtp or rusender")
    if args.evidence_output and args.mail_gateway_smoke and not args.expected_mail_provider:
        raise SmokeFailure(
            "structured mail gateway evidence requires SMOKE_EXPECTED_MAIL_PROVIDER"
        )
    if args.evidence_output:
        commit = str(args.commit or "").strip().lower()
        if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
            raise SmokeFailure(
                "structured smoke evidence requires --commit/RELEASE_SHA as a full Git SHA"
            )
        args.commit = commit
        environment = str(args.environment or "").strip()
        if not environment:
            raise SmokeFailure(
                "structured smoke evidence requires --environment/ACCEPTANCE_ENVIRONMENT"
            )
        args.environment = environment

    checks: dict[str, bool] = {
        "public_health_legal": False,
        "disposable_registration": False,
        "email_verification": False,
        "password_reset": False,
        "password_reset_throttle": False,
        "password_reset_session_revoked": False,
        "demo_activation": False,
        "legal_consent_evidence": False,
        "disposable_refresh_restore": False,
        "deactivation": False,
        "inactive_login_rejected": False,
        "authenticated_profile": False,
        "authenticated_refresh_restore": False,
        "dashboard_contract": False,
        "mail_gateway_ready": False,
        "audit_correlation": False,
        "wb_credential": False,
        "billing_init": False,
        "logout_session_revoke": False,
    }

    mail_gateway_evidence: dict | None = None
    client = SmokeClient(args.base_url)
    run_public_smoke(client, args.expected_version)
    checks["public_health_legal"] = True

    if args.public_only:
        if args.evidence_output:
            _write_evidence(
                args.evidence_output,
                args=args,
                checks=checks,
                mail_gateway=mail_gateway_evidence,
            )
        return 0

    if not args.email or not args.password:
        raise SmokeFailure("SMOKE_EMAIL and SMOKE_PASSWORD are required for authenticated smoke")

    if args.mail_gateway_smoke:
        mail_gateway_evidence = run_mail_gateway_authenticated_preflight(
            args.base_url,
            email=args.email,
            password=args.password,
            expected_provider=args.expected_mail_provider,
            require_email_verification=args.require_email_verification,
            require_password_reset=args.require_password_reset,
        )
        checks["mail_gateway_ready"] = True

    if not args.skip_disposable_registration:
        disposable = run_disposable_registration_smoke(
            args.base_url,
            email_template=args.disposable_email_template,
            mail_token_command=args.mail_token_command,
            mail_token_timeout=args.mail_token_timeout,
            require_email_verification=args.require_email_verification,
            require_password_reset=args.require_password_reset,
            mail_admin_email=args.email,
            mail_admin_password=args.password,
        )
        checks.update(disposable)
        checks["disposable_refresh_restore"] = disposable["refresh_restore"]
        checks.pop("refresh_restore", None)

    authenticated_error: SmokeFailure | None = None
    try:
        run_authenticated_smoke(client, args.email, args.password)
        checks["authenticated_profile"] = True
        checks["authenticated_refresh_restore"] = True
        checks["dashboard_contract"] = True
        if args.audit_smoke:
            run_audit_correlation_smoke(client)
            checks["audit_correlation"] = True
        if args.wb_token:
            run_wb_credential_smoke(client, args.wb_token)
            checks["wb_credential"] = True
        if args.billing_tariff:
            run_billing_init_smoke(client, args.billing_tariff)
            checks["billing_init"] = True
    except SmokeFailure as exc:
        authenticated_error = exc
    finally:
        # Once login succeeds, always revoke the refresh session even when a
        # later audit/WB/billing assertion fails. This keeps repeated release
        # acceptance runs from leaving reusable authenticated sessions behind.
        if client.access_token or any(True for _ in client.cookies):
            try:
                run_logout_smoke(client)
                checks["logout_session_revoke"] = True
            except SmokeFailure as cleanup_exc:
                if authenticated_error is not None:
                    raise SmokeFailure(
                        f"{authenticated_error}; authenticated smoke logout cleanup also failed"
                    ) from cleanup_exc
                raise

    if authenticated_error is not None:
        raise authenticated_error

    if args.evidence_output:
        _write_evidence(
            args.evidence_output,
            args=args,
            checks=checks,
            mail_gateway=mail_gateway_evidence,
        )
        print(f"[ok] structured release smoke evidence: {args.evidence_output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as exc:
        print(f"[failed] {exc}", file=sys.stderr)
        raise SystemExit(1)
