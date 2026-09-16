#!/usr/bin/env python3
"""Collect secret-safe payment-provider isolation evidence for WB Insight beta acceptance.

The runner is read-only: it logs in with an existing Control Panel account, inspects
provider configuration and journal filters, and never creates or mutates payments.
Passwords, cookies, JWTs, credential hints and provider configuration values are not
written to the evidence report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from release_smoke import SmokeClient, SmokeFailure


SHA40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_CHECKS = {
    "provider_catalog_read",
    "unique_provider_mode_pairs",
    "secret_fields_absent",
    "provider_urls_safe",
    "sber_test_live_separated",
    "fake_disabled_in_production",
    "single_live_default",
    "journal_test_filter_isolated",
    "journal_live_filter_isolated",
}
FORBIDDEN_KEY_FRAGMENTS = ("password", "secret", "token", "authorization")
SAFE_CREDENTIAL_KEYS = {"credentials_configured", "credential_hint"}


class PaymentAcceptanceError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _project_version(project: Path) -> str:
    path = project / "VERSION"
    if not path.is_file():
        raise PaymentAcceptanceError("VERSION is missing")
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise PaymentAcceptanceError("VERSION is empty")
    return value


def _project_commit(project: Path) -> str:
    import subprocess

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project,
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PaymentAcceptanceError("unable to read Git HEAD") from exc
    commit = completed.stdout.strip()
    if completed.returncode != 0 or SHA40_RE.fullmatch(commit) is None:
        raise PaymentAcceptanceError("Git HEAD is not a full commit SHA")
    return commit.lower()


def _safe_https_origin(value: str) -> str:
    parsed = urlparse(value.strip())
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise PaymentAcceptanceError("payment acceptance requires a public HTTPS origin")
    port = f":{parsed.port}" if parsed.port else ""
    return f"https://{parsed.hostname}{port}"


def _has_sensitive_key(value: Any) -> bool:
    if isinstance(value, dict):
        for raw_key, item in value.items():
            key = str(raw_key).lower()
            if key not in SAFE_CREDENTIAL_KEYS and (
                "credential" in key or any(fragment in key for fragment in FORBIDDEN_KEY_FRAGMENTS)
            ):
                return True
            if _has_sensitive_key(item):
                return True
    elif isinstance(value, list):
        return any(_has_sensitive_key(item) for item in value)
    return False


def _safe_url(value: object) -> bool:
    if value in (None, ""):
        return True
    parsed = urlparse(str(value))
    return bool(
        parsed.scheme in {"http", "https"}
        and parsed.hostname
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
    )


def _validate_provider_payload(providers: object) -> dict[str, Any]:
    if not isinstance(providers, list) or not providers:
        raise PaymentAcceptanceError("payment provider catalog is empty")
    if _has_sensitive_key(providers):
        raise PaymentAcceptanceError("payment provider API exposed a secret-like field")

    pairs: set[tuple[str, str]] = set()
    defaults: list[tuple[str, str]] = []
    sber_modes: dict[str, dict[str, Any]] = {}
    fake_test: dict[str, Any] | None = None

    for item in providers:
        if not isinstance(item, dict):
            raise PaymentAcceptanceError("payment provider catalog contains an invalid item")
        provider = str(item.get("provider") or "").strip().lower()
        mode = str(item.get("mode") or "").strip().lower()
        if not provider or mode not in {"test", "live"}:
            raise PaymentAcceptanceError("payment provider catalog contains an invalid provider/mode")
        pair = (provider, mode)
        if pair in pairs:
            raise PaymentAcceptanceError("payment provider catalog contains duplicate provider/mode")
        pairs.add(pair)

        for field in ("api_base_url", "return_url", "fail_url"):
            if not _safe_url(item.get(field)):
                raise PaymentAcceptanceError(f"payment provider {provider}/{mode} has unsafe {field}")

        if item.get("is_default") is True:
            defaults.append(pair)
            if mode != "live":
                raise PaymentAcceptanceError("production-like default payment provider must use live mode")
        if provider == "sber":
            sber_modes[mode] = item
        if pair == ("fake", "test"):
            fake_test = item

    if set(sber_modes) != {"test", "live"}:
        raise PaymentAcceptanceError("Sber test/live configurations are not both visible")
    if sber_modes["test"].get("source") == "environment":
        raise PaymentAcceptanceError("Sber test mode inherited live environment credentials")
    if fake_test is None:
        raise PaymentAcceptanceError("fake/test provider contract is missing")
    if fake_test.get("enabled") is True or fake_test.get("ready") is True or fake_test.get("is_default") is True:
        raise PaymentAcceptanceError("fake payment provider is active in production-like acceptance")
    if len(defaults) > 1:
        raise PaymentAcceptanceError("more than one default payment provider is configured")

    return {
        "provider_count": len(providers),
        "provider_mode_pair_count": len(pairs),
        "default_provider": "/".join(defaults[0]) if defaults else None,
        "sber_test_source": str(sber_modes["test"].get("source") or "unknown"),
        "sber_live_source": str(sber_modes["live"].get("source") or "unknown"),
    }


def _validate_journal_mode(payload: dict[str, Any], expected_mode: str) -> int:
    if payload.get("status") != "success":
        raise PaymentAcceptanceError(f"payment journal {expected_mode} filter failed")
    payments = payload.get("payments")
    if not isinstance(payments, list):
        raise PaymentAcceptanceError("payment journal returned an invalid payments list")
    for item in payments:
        if not isinstance(item, dict) or item.get("mode") != expected_mode:
            raise PaymentAcceptanceError(f"payment journal leaked non-{expected_mode} row through mode filter")
        if _has_sensitive_key(item):
            raise PaymentAcceptanceError("payment journal list exposed a secret-like field")
    return len(payments)


def validate_payment_evidence(
    path: Path,
    *,
    version: str,
    commit: str,
    environment: str,
) -> None:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PaymentAcceptanceError("payment isolation proof must be valid UTF-8 JSON") from exc
    if not isinstance(report, dict):
        raise PaymentAcceptanceError("payment isolation proof must contain a JSON object")
    if report.get("schema_version") != 1 or report.get("kind") != "payment_isolation":
        raise PaymentAcceptanceError("payment isolation proof has an invalid schema")
    if report.get("status") != "pass":
        raise PaymentAcceptanceError("payment isolation proof did not pass")
    if report.get("version") != version:
        raise PaymentAcceptanceError("payment isolation proof VERSION does not match release")
    if str(report.get("commit") or "").lower() != commit.lower():
        raise PaymentAcceptanceError("payment isolation proof commit does not match release")
    if report.get("environment") != environment:
        raise PaymentAcceptanceError("payment isolation proof environment does not match release")
    _safe_https_origin(str(report.get("base_origin") or ""))
    checks = report.get("checks")
    if not isinstance(checks, dict):
        raise PaymentAcceptanceError("payment isolation proof is missing checks")
    missing = sorted(name for name in REQUIRED_CHECKS if checks.get(name) is not True)
    if missing:
        raise PaymentAcceptanceError("payment isolation proof is missing checks: " + ", ".join(missing))


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _self_test() -> None:
    providers = [
        {
            "provider": "sber",
            "mode": "test",
            "enabled": False,
            "is_default": False,
            "ready": False,
            "source": "unconfigured",
            "api_base_url": "https://sandbox.example.com/api",
            "return_url": None,
            "fail_url": None,
            "credentials_configured": False,
            "credential_hint": None,
            "options": {},
        },
        {
            "provider": "sber",
            "mode": "live",
            "enabled": True,
            "is_default": True,
            "ready": True,
            "source": "database",
            "api_base_url": "https://payments.example.com/api",
            "return_url": "https://app.example.com/billing/success",
            "fail_url": "https://app.example.com/billing/fail",
            "credentials_configured": True,
            "credential_hint": "ab••••cd",
            "options": {},
        },
        {
            "provider": "fake",
            "mode": "test",
            "enabled": False,
            "is_default": False,
            "ready": False,
            "source": "unconfigured",
            "options": {},
        },
    ]
    summary = _validate_provider_payload(providers)
    assert summary["default_provider"] == "sber/live"
    assert _validate_journal_mode({"status": "success", "payments": [{"mode": "test"}]}, "test") == 1

    leaked = [dict(providers[0], password="oops"), *providers[1:]]
    try:
        _validate_provider_payload(leaked)
    except PaymentAcceptanceError:
        pass
    else:
        raise AssertionError("secret-like provider field unexpectedly passed")
    print("[ok] payment isolation acceptance self-test")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path(os.getenv("PROJECT_DIR", "/home/projects/wb")))
    parser.add_argument("--base-url", default=os.getenv("SMOKE_BASE_URL"))
    parser.add_argument("--email", default=os.getenv("SMOKE_EMAIL"))
    parser.add_argument("--password", default=os.getenv("SMOKE_PASSWORD"))
    parser.add_argument("--environment", default=os.getenv("ACCEPTANCE_ENVIRONMENT"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return 0
    if not args.base_url:
        raise PaymentAcceptanceError("--base-url or SMOKE_BASE_URL is required")
    if not args.email or not args.password:
        raise PaymentAcceptanceError("SMOKE_EMAIL and SMOKE_PASSWORD are required")
    if not args.environment or not args.environment.strip():
        raise PaymentAcceptanceError("--environment or ACCEPTANCE_ENVIRONMENT is required")
    if args.output is None:
        raise PaymentAcceptanceError("--output is required")

    project = args.project_dir.resolve()
    version = _project_version(project)
    commit = _project_commit(project)
    origin = _safe_https_origin(args.base_url)
    checks = {name: False for name in sorted(REQUIRED_CHECKS)}
    report: dict[str, Any] = {
        "schema_version": 1,
        "kind": "payment_isolation",
        "status": "fail",
        "version": version,
        "commit": commit,
        "environment": args.environment.strip(),
        "base_origin": origin,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }

    try:
        client = SmokeClient(origin)
        live = client.request("GET", "/health/live")
        if live.get("status") != "ok" or live.get("version") != version:
            raise PaymentAcceptanceError("deployed health/version does not match local release")

        login = client.request("POST", "/auth/login", body={"email": args.email, "password": args.password})
        if login.get("status") != "success" or not login.get("access_token"):
            raise PaymentAcceptanceError("Control Panel login failed")
        client.access_token = login["access_token"]

        providers_payload = client.request("GET", "/control-panel/payments/providers", auth=True)
        if providers_payload.get("status") != "success":
            raise PaymentAcceptanceError("Control Panel payment provider API failed")
        summary = _validate_provider_payload(providers_payload.get("providers"))
        for name in (
            "provider_catalog_read",
            "unique_provider_mode_pairs",
            "secret_fields_absent",
            "provider_urls_safe",
            "sber_test_live_separated",
            "fake_disabled_in_production",
            "single_live_default",
        ):
            checks[name] = True

        test_count = _validate_journal_mode(
            client.request("GET", "/control-panel/payments/journal?mode=test&limit=100", auth=True),
            "test",
        )
        checks["journal_test_filter_isolated"] = True
        live_count = _validate_journal_mode(
            client.request("GET", "/control-panel/payments/journal?mode=live&limit=100", auth=True),
            "live",
        )
        checks["journal_live_filter_isolated"] = True

        client.request("POST", "/auth/logout", auth=True, body={})
        client.access_token = None

        report.update(
            {
                "status": "pass",
                "provider_count": summary["provider_count"],
                "provider_mode_pair_count": summary["provider_mode_pair_count"],
                "default_provider": summary["default_provider"],
                "journal_test_rows_checked": test_count,
                "journal_live_rows_checked": live_count,
            }
        )
        _write_report(args.output, report)
        print(f"[ok] structured payment isolation evidence: {args.output}")
        return 0
    except (PaymentAcceptanceError, SmokeFailure, OSError, UnicodeDecodeError) as exc:
        report["error"] = str(exc)
        try:
            _write_report(args.output, report)
        except OSError:
            pass
        print(f"[failed] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PaymentAcceptanceError as exc:
        print(f"[failed] {exc}", file=sys.stderr)
        raise SystemExit(1)
