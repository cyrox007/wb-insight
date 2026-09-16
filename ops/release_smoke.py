#!/usr/bin/env python3
"""WB Insight production-like release smoke runner.

The runner intentionally never prints passwords, access tokens, refresh cookies or
marketplace credentials. It verifies disposable registration before the core
pre-provisioned-user smoke unless explicitly disabled. Optional WB and billing
phases are enabled only when their environment variables are supplied.
"""

from __future__ import annotations

import argparse
from http.cookiejar import CookieJar
from pathlib import Path
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4


class SmokeFailure(RuntimeError):
    pass


class SmokeClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
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


def _env_flag(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


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


def run_disposable_registration_smoke(base_url: str) -> None:
    """Prove registration/demo/consent/session lifecycle with an isolated account."""
    client = SmokeClient(base_url)
    suffix = uuid4()
    email = f"release-smoke+{suffix.hex}@smoke.invalid"
    phone = f"+7{suffix.int % 10_000_000_000:010d}"
    password = f"Smoke-{suffix.hex[:12]}-A7!"
    required_consents = _required_consents(client, "registration")
    expected_evidence = {
        (item["code"], item["version"], item["sha256"])
        for item in required_consents
    }

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
            }
        },
    )
    if registration.get("status") != "success":
        raise SmokeFailure("disposable registration did not succeed")

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

    deactivated = False
    try:
        profile = client.request("GET", "/dashboard/profile/", auth=True)
        subscription = profile.get("subscription") or {}
        if subscription.get("status") != "demo" or subscription.get("is_active") is not True:
            raise SmokeFailure("registration did not create an active demo subscription")

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
        if client.access_token and not deactivated:
            try:
                client.request(
                    "POST",
                    "/account/deactivate",
                    auth=True,
                    body={"reason": "release smoke cleanup after failure"},
                )
            except SmokeFailure:
                pass
            client.access_token = None

    print("[ok] disposable registration, demo subscription, consent evidence, refresh and deactivation")


def run_authenticated_smoke(client: SmokeClient, email: str, password: str) -> None:
    login = client.request(
        "POST",
        "/auth/login",
        body={"email": email, "password": password},
    )
    if login.get("status") != "success" or not login.get("access_token") or not login.get("user"):
        raise SmokeFailure("login did not return access token and user identity")
    client.access_token = login["access_token"]
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
        created_id = created.get("data", {}).get("id")
        if not created_id:
            raise SmokeFailure("WB credential smoke did not return credential id")
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
    client.request("POST", "/auth/logout", auth=True, body={})
    client.access_token = None
    payload = client.request("POST", "/auth/refresh", body={}, expected=(401,))
    if payload.get("error", {}).get("code") not in {"INVALID_TOKEN", "SESSION_REVOKED"}:
        raise SmokeFailure("refresh after logout did not return the expected session error")
    print("[ok] logout clears refresh session")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run WB Insight production-like release smoke")
    parser.add_argument("--base-url", default=os.getenv("SMOKE_BASE_URL"))
    parser.add_argument("--email", default=os.getenv("SMOKE_EMAIL"))
    parser.add_argument("--password", default=os.getenv("SMOKE_PASSWORD"))
    parser.add_argument(
        "--expected-version",
        default=os.getenv("SMOKE_EXPECTED_VERSION") or _project_version(),
    )
    parser.add_argument("--public-only", action="store_true")
    parser.add_argument(
        "--skip-disposable-registration",
        action="store_true",
        default=_env_flag("SMOKE_SKIP_DISPOSABLE_REGISTRATION"),
        help="Skip disposable registration/demo/consent lifecycle verification",
    )
    parser.add_argument("--wb-token", default=os.getenv("SMOKE_WB_TOKEN"))
    parser.add_argument("--billing-tariff", default=os.getenv("SMOKE_BILLING_TARIFF"))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.base_url:
        raise SmokeFailure("SMOKE_BASE_URL or --base-url is required")

    client = SmokeClient(args.base_url)
    run_public_smoke(client, args.expected_version)

    if args.public_only:
        return 0

    if not args.skip_disposable_registration:
        run_disposable_registration_smoke(args.base_url)

    if not args.email or not args.password:
        raise SmokeFailure("SMOKE_EMAIL and SMOKE_PASSWORD are required for authenticated smoke")

    run_authenticated_smoke(client, args.email, args.password)
    if args.wb_token:
        run_wb_credential_smoke(client, args.wb_token)
    if args.billing_tariff:
        run_billing_init_smoke(client, args.billing_tariff)
    run_logout_smoke(client)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as exc:
        print(f"[failed] {exc}", file=sys.stderr)
        raise SystemExit(1)
