#!/usr/bin/env python3
"""Collect secret-safe Sber sandbox merchant evidence for WB Insight P40.

The runner creates one unpaid sandbox order through the production Sber adapter and
queries its status. It never submits card data, never marks the order paid, and does
not write merchant credentials, gateway order ids or payment-form URLs to evidence.

Merchant credentials are accepted only from environment variables:
SBER_TEST_API_BASE_URL, SBER_TEST_USERNAME and SBER_TEST_PASSWORD.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4


SHA40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
REQUIRED_CHECKS = {
    "sandbox_https_config",
    "merchant_credentials_accepted",
    "order_registered",
    "confirmation_url_https",
    "status_query_succeeded",
    "order_not_paid",
    "secret_material_not_recorded",
}


class SberSandboxAcceptanceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "SBER_SANDBOX_ACCEPTANCE_ERROR") -> None:
        super().__init__(message)
        self.code = code


def _project_identity(project: Path) -> tuple[str, str]:
    version_path = project / "VERSION"
    if not version_path.is_file():
        raise SberSandboxAcceptanceError("VERSION is missing")
    version = version_path.read_text(encoding="utf-8").strip()
    if not version:
        raise SberSandboxAcceptanceError("VERSION is empty")
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
        raise SberSandboxAcceptanceError("unable to read Git HEAD") from exc
    commit = completed.stdout.strip()
    if completed.returncode != 0 or SHA40_RE.fullmatch(commit) is None:
        raise SberSandboxAcceptanceError("Git HEAD is not a full commit SHA")
    return version, commit.lower()


def _public_origin(value: str) -> str:
    parsed = urlparse(value.strip())
    try:
        parsed_port = parsed.port
    except ValueError as exc:
        raise SberSandboxAcceptanceError("public origin contains an invalid port") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/", "/api", "/api/"}
    ):
        raise SberSandboxAcceptanceError(
            "public origin must be HTTPS and may only use an optional /api suffix"
        )
    port = f":{parsed_port}" if parsed_port else ""
    return f"https://{parsed.hostname}{port}"


def _gateway_base_url(value: str) -> str:
    parsed = urlparse(value.strip())
    try:
        parsed_port = parsed.port
    except ValueError as exc:
        raise SberSandboxAcceptanceError(
            "SBER_TEST_API_BASE_URL contains an invalid port"
        ) from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise SberSandboxAcceptanceError(
            "SBER_TEST_API_BASE_URL must be an HTTPS URL without credentials/query/fragment"
        )
    path = parsed.path.rstrip("/")
    port = f":{parsed_port}" if parsed_port else ""
    return f"https://{parsed.hostname}{port}{path}"


def _safe_confirmation_url(value: str) -> bool:
    parsed = urlparse(value.strip())
    return bool(
        parsed.scheme == "https"
        and parsed.hostname
        and not parsed.username
        and not parsed.password
    )


def _report_has_secret_material(report: dict[str, Any], secrets: tuple[str, ...]) -> bool:
    serialized = json.dumps(report, ensure_ascii=False, sort_keys=True)
    return any(secret and secret in serialized for secret in secrets)


def validate_sber_sandbox_evidence(
    path: Path,
    *,
    version: str,
    commit: str,
    environment: str,
    public_origin: str | None = None,
) -> dict[str, Any]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SberSandboxAcceptanceError("Sber sandbox proof must be valid UTF-8 JSON") from exc
    if not isinstance(report, dict):
        raise SberSandboxAcceptanceError("Sber sandbox proof must contain a JSON object")
    if report.get("schema_version") != 1 or report.get("kind") != "sber_sandbox":
        raise SberSandboxAcceptanceError("Sber sandbox proof has an invalid schema")
    if report.get("status") != "pass":
        raise SberSandboxAcceptanceError("Sber sandbox proof did not pass")
    if report.get("version") != version:
        raise SberSandboxAcceptanceError("Sber sandbox proof VERSION does not match release")
    if str(report.get("commit") or "").lower() != commit.lower():
        raise SberSandboxAcceptanceError("Sber sandbox proof commit does not match release")
    if report.get("environment") != environment:
        raise SberSandboxAcceptanceError("Sber sandbox proof environment does not match release")
    evidence_origin = _public_origin(str(report.get("public_origin") or ""))
    if public_origin is not None and evidence_origin != _public_origin(public_origin):
        raise SberSandboxAcceptanceError("Sber sandbox proof public origin does not match release")
    checks = report.get("checks")
    if not isinstance(checks, dict):
        raise SberSandboxAcceptanceError("Sber sandbox proof is missing checks")
    missing = sorted(name for name in REQUIRED_CHECKS if checks.get(name) is not True)
    if missing:
        raise SberSandboxAcceptanceError(
            "Sber sandbox proof is missing checks: " + ", ".join(missing)
        )
    return report


async def _execute_gateway_probe(
    *,
    project: Path,
    gateway_url: str,
    username: str,
    password: str,
    public_origin: str,
    amount_kopecks: int,
    currency: str,
    status_attempts: int,
    status_delay_seconds: float,
) -> dict[str, bool]:
    backend = project / "backend"
    if not backend.is_dir():
        raise SberSandboxAcceptanceError("backend directory is missing")
    sys.path.insert(0, str(backend))
    try:
        from integrations.sber.client import SberAcquiringClient, SberAcquiringError
    except Exception as exc:
        raise SberSandboxAcceptanceError(
            "unable to import the deployed Sber adapter; run with the project backend venv"
        ) from exc

    order_number = (
        "WBI-ACCEPT-"
        + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        + "-"
        + uuid4().hex[:10].upper()
    )
    return_url = f"{public_origin}/billing/success?acceptance=sber-sandbox"
    fail_url = f"{public_origin}/billing/success?acceptance=sber-sandbox-fail"

    try:
        async with SberAcquiringClient(
            base_url=gateway_url,
            username=username,
            password=password,
            timeout_seconds=15.0,
        ) as client:
            registered = await client.register_order(
                order_number=order_number,
                amount_kopecks=amount_kopecks,
                currency=currency,
                return_url=return_url,
                fail_url=fail_url,
                description="WB Insight P40 sandbox acceptance",
            )
            if not registered.order_id:
                raise SberSandboxAcceptanceError("Sber sandbox did not return an order id")
            if not _safe_confirmation_url(registered.form_url):
                raise SberSandboxAcceptanceError(
                    "Sber sandbox returned a non-HTTPS or credential-bearing payment-form URL"
                )

            status_result = None
            last_error = None
            for attempt in range(status_attempts):
                try:
                    status_result = await client.get_order_status(order_id=registered.order_id)
                    break
                except SberAcquiringError as exc:
                    last_error = exc
                    if attempt + 1 < status_attempts:
                        await asyncio.sleep(status_delay_seconds)
            if status_result is None:
                code = getattr(last_error, "code", "SBER_STATUS_UNAVAILABLE")
                raise SberSandboxAcceptanceError(
                    "registered sandbox order could not be queried",
                    code=str(code),
                )
            if status_result.is_paid:
                raise SberSandboxAcceptanceError(
                    "sandbox acceptance order unexpectedly reached paid state",
                    code="SBER_SANDBOX_ORDER_UNEXPECTEDLY_PAID",
                )
    except SberSandboxAcceptanceError:
        raise
    except SberAcquiringError as exc:
        raise SberSandboxAcceptanceError(
            "Sber sandbox rejected the merchant probe",
            code=str(getattr(exc, "code", "SBER_ACQUIRING_ERROR")),
        ) from exc

    return {
        "merchant_credentials_accepted": True,
        "order_registered": True,
        "confirmation_url_https": True,
        "status_query_succeeded": True,
        "order_not_paid": True,
    }


def _write(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _self_test() -> None:
    assert _public_origin("https://example.test") == "https://example.test"
    assert _public_origin("https://example.test/api") == "https://example.test"
    assert _gateway_base_url("https://sandbox.example.test/payment/rest/") == (
        "https://sandbox.example.test/payment/rest"
    )
    assert _safe_confirmation_url(
        "https://secure.example.test/payment/merchants/sbersafe_sberid/payment_ru.html?mdOrder=x"
    )
    for invalid in (
        "http://example.test",
        "https://user:pass@example.test",
        "https://example.test/path",
        "https://example.test/?token=x",
        "https://example.test:bad-port",
    ):
        try:
            _public_origin(invalid)
        except SberSandboxAcceptanceError:
            pass
        else:
            raise AssertionError(f"invalid public origin unexpectedly passed: {invalid}")

    try:
        _gateway_base_url("https://sandbox.example.test:bad-port/payment/rest")
    except SberSandboxAcceptanceError:
        pass
    else:
        raise AssertionError("invalid sandbox gateway port unexpectedly passed")

    fixture = {
        "schema_version": 1,
        "kind": "sber_sandbox",
        "status": "pass",
        "version": "0.9.0-beta.1",
        "commit": "0" * 40,
        "environment": "staging-ci",
        "public_origin": "https://example.test",
        "checks": {name: True for name in REQUIRED_CHECKS},
    }
    assert not _report_has_secret_material(
        fixture,
        ("sandbox-user-secret", "sandbox-password-secret"),
    )
    with TemporaryDirectory() as raw_tmp:
        proof = Path(raw_tmp) / "sber-sandbox.json"
        _write(proof, fixture)
        validate_sber_sandbox_evidence(
            proof,
            version="0.9.0-beta.1",
            commit="0" * 40,
            environment="staging-ci",
            public_origin="https://example.test",
        )
        try:
            validate_sber_sandbox_evidence(
                proof,
                version="0.9.0-beta.1",
                commit="0" * 40,
                environment="staging-ci",
                public_origin="https://other.example.test",
            )
        except SberSandboxAcceptanceError:
            pass
        else:
            raise AssertionError("mismatched public origin unexpectedly passed")
    print("[ok] Sber sandbox acceptance self-test")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-dir",
        type=Path,
        default=Path(os.getenv("PROJECT_DIR", "/home/projects/wb")),
    )
    parser.add_argument("--environment", default=os.getenv("ACCEPTANCE_ENVIRONMENT"))
    parser.add_argument("--public-origin", default=os.getenv("SMOKE_BASE_URL"))
    parser.add_argument("--amount-kopecks", type=int, default=100)
    parser.add_argument("--currency", default="643")
    parser.add_argument("--status-attempts", type=int, default=3)
    parser.add_argument("--status-delay-seconds", type=float, default=1.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return 0

    environment = str(args.environment or "").strip()
    if not environment:
        raise SberSandboxAcceptanceError(
            "--environment or ACCEPTANCE_ENVIRONMENT is required"
        )
    if not args.public_origin:
        raise SberSandboxAcceptanceError(
            "--public-origin or SMOKE_BASE_URL is required"
        )
    if args.output is None:
        raise SberSandboxAcceptanceError("--output is required")
    if args.amount_kopecks <= 0 or args.amount_kopecks > 100000:
        raise SberSandboxAcceptanceError(
            "--amount-kopecks must be between 1 and 100000"
        )
    if not re.fullmatch(r"\d{3}", str(args.currency)):
        raise SberSandboxAcceptanceError("--currency must be a three-digit code")
    if args.status_attempts < 1 or args.status_attempts > 10:
        raise SberSandboxAcceptanceError("--status-attempts must be between 1 and 10")
    if args.status_delay_seconds < 0 or args.status_delay_seconds > 10:
        raise SberSandboxAcceptanceError(
            "--status-delay-seconds must be between 0 and 10"
        )

    username = os.getenv("SBER_TEST_USERNAME", "").strip()
    password = os.getenv("SBER_TEST_PASSWORD", "").strip()
    raw_gateway_url = os.getenv("SBER_TEST_API_BASE_URL", "").strip()
    if not username or not password or not raw_gateway_url:
        raise SberSandboxAcceptanceError(
            "SBER_TEST_API_BASE_URL, SBER_TEST_USERNAME and SBER_TEST_PASSWORD are required"
        )

    project = args.project_dir.resolve()
    version, commit = _project_identity(project)
    public_origin = _public_origin(str(args.public_origin))
    gateway_url = _gateway_base_url(raw_gateway_url)
    checks = {name: False for name in sorted(REQUIRED_CHECKS)}
    checks["sandbox_https_config"] = True

    report: dict[str, Any] = {
        "schema_version": 1,
        "kind": "sber_sandbox",
        "status": "fail",
        "version": version,
        "commit": commit,
        "environment": environment,
        "public_origin": public_origin,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "amount_kopecks": args.amount_kopecks,
        "currency": str(args.currency),
        "checks": checks,
    }

    try:
        probe_checks = asyncio.run(
            _execute_gateway_probe(
                project=project,
                gateway_url=gateway_url,
                username=username,
                password=password,
                public_origin=public_origin,
                amount_kopecks=args.amount_kopecks,
                currency=str(args.currency),
                status_attempts=args.status_attempts,
                status_delay_seconds=args.status_delay_seconds,
            )
        )
        checks.update(probe_checks)
        if _report_has_secret_material(report, (username, password, raw_gateway_url)):
            raise SberSandboxAcceptanceError(
                "evidence serialization unexpectedly contains configured secret material",
                code="SBER_SANDBOX_EVIDENCE_SECRET_LEAK",
            )
        checks["secret_material_not_recorded"] = True
        report["status"] = "pass"
        _write(args.output, report)
        validate_sber_sandbox_evidence(
            args.output,
            version=version,
            commit=commit,
            environment=environment,
            public_origin=public_origin,
        )
        print(f"[ok] structured Sber sandbox evidence: {args.output}")
        return 0
    except SberSandboxAcceptanceError as exc:
        report["error_code"] = exc.code
        try:
            _write(args.output, report)
        except OSError:
            pass
        print(f"[failed] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SberSandboxAcceptanceError as exc:
        print(f"[failed] {exc}", file=sys.stderr)
        raise SystemExit(1)
