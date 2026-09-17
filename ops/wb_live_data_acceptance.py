#!/usr/bin/env python3
"""Prove that beta data-accuracy evidence belongs to a live WB account.

The runner performs a temporary production-like WB credential validation through the
public API, derives a keyed HMAC fingerprint from the returned external account id,
removes the temporary credential, and binds that fingerprint to a passing
 data-accuracy input/report pair.

Passwords, JWTs, WB tokens, fingerprint keys, external account ids and seller values
are never written to the evidence artifact. Secret inputs are accepted from
environment variables only so they do not need to appear in shell history/process
arguments.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from datetime import datetime, timezone
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPCookieProcessor, Request, build_opener
from uuid import uuid4

from release_evidence import SHA40_RE, SHA256_RE, validate_data_accuracy


class WBLiveDataAcceptanceError(RuntimeError):
    pass


class _Client:
    def __init__(self, base_origin: str):
        self.base_origin = _https_origin(base_origin)
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
        expected: tuple[int, ...] = (200,),
    ) -> dict:
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if auth:
            if not self.access_token:
                raise WBLiveDataAcceptanceError("authenticated request has no access token")
            headers["Authorization"] = f"Bearer {self.access_token}"
        request = Request(f"{self.base_origin}{path}", data=data, headers=headers, method=method)
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
            raise WBLiveDataAcceptanceError(f"{method} {path}: endpoint unavailable") from exc
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WBLiveDataAcceptanceError(f"{method} {path}: non-JSON response") from exc
        if status not in expected:
            code = None
            if isinstance(payload, dict) and isinstance(payload.get("error"), dict):
                code = payload["error"].get("code")
            suffix = f" ({code})" if code else ""
            raise WBLiveDataAcceptanceError(f"{method} {path}: HTTP {status}{suffix}")
        if not isinstance(payload, dict):
            raise WBLiveDataAcceptanceError(f"{method} {path}: invalid API envelope")
        return payload


def _https_origin(value: str) -> str:
    parsed = urlparse(str(value or "").strip())
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise WBLiveDataAcceptanceError("base URL must be a public HTTPS origin")
    port = f":{parsed.port}" if parsed.port else ""
    return f"https://{parsed.hostname}{port}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _account_fingerprint(external_account_id: object, fingerprint_key: str) -> str:
    value = str(external_account_id or "").strip()
    key = fingerprint_key.encode("utf-8")
    if not value or len(value) > 512:
        raise WBLiveDataAcceptanceError("WB validation did not return a usable external account id")
    if len(key) < 16:
        raise WBLiveDataAcceptanceError("WB_ACCEPTANCE_FINGERPRINT_KEY must be at least 16 bytes")
    return hmac.new(key, f"wb-account-v1:{value}".encode("utf-8"), hashlib.sha256).hexdigest()


def _load_object(path: Path, *, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WBLiveDataAcceptanceError(f"{label} must be valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise WBLiveDataAcceptanceError(f"{label} must contain a JSON object")
    return value


def _required_consents(client: _Client) -> list[dict]:
    payload = client.request("GET", "/legal/requirements/marketplace_credential")
    documents = payload.get("documents")
    if not isinstance(documents, list) or not documents:
        raise WBLiveDataAcceptanceError("marketplace credential legal requirements are unavailable")
    result: list[dict] = []
    for document in documents:
        if not isinstance(document, dict):
            raise WBLiveDataAcceptanceError("marketplace credential legal requirements are invalid")
        for field in ("code", "version", "sha256"):
            if not str(document.get(field) or "").strip():
                raise WBLiveDataAcceptanceError("marketplace credential legal requirement is incomplete")
        result.append(
            {
                "code": document["code"],
                "version": document["version"],
                "sha256": document["sha256"],
                "accepted": True,
            }
        )
    return result


def _login(client: _Client, email: str, password: str) -> None:
    payload = client.request("POST", "/auth/login", body={"email": email, "password": password})
    token = payload.get("access_token")
    if payload.get("status") != "success" or not isinstance(token, str) or not token:
        raise WBLiveDataAcceptanceError("acceptance account login failed")
    client.access_token = token


def _probe_live_account(
    *,
    base_origin: str,
    email: str,
    password: str,
    wb_token: str,
    fingerprint_key: str,
) -> str:
    client = _Client(base_origin)
    _login(client, email, password)
    consents = _required_consents(client)
    created_id: str | None = None
    account_fingerprint: str | None = None
    cleanup_complete = False
    try:
        created = client.request(
            "POST",
            "/dashboard/tokens",
            auth=True,
            body={
                "token": wb_token,
                "label": f"beta-acceptance-{uuid4().hex[:8]}",
                "legal_consents": consents,
            },
        )
        data = created.get("data")
        if created.get("status") != "success" or not isinstance(data, dict):
            raise WBLiveDataAcceptanceError("temporary WB credential validation failed")
        created_id = str(data.get("id") or "").strip() or None
        if created_id is None:
            raise WBLiveDataAcceptanceError("temporary WB credential id is missing")
        account_fingerprint = _account_fingerprint(
            data.get("external_account_id"),
            fingerprint_key,
        )
    finally:
        if created_id:
            deleted = client.request(
                "DELETE",
                f"/dashboard/profile/token/{created_id}",
                auth=True,
            )
            cleanup_complete = deleted.get("status") == "success"
            if not cleanup_complete:
                raise WBLiveDataAcceptanceError("temporary WB credential cleanup failed")

    if account_fingerprint is None or not cleanup_complete:
        raise WBLiveDataAcceptanceError("live WB validation did not complete safely")
    return account_fingerprint


def _validate_accuracy_pair(
    input_path: Path,
    report_path: Path,
    *,
    account_fingerprint: str,
) -> dict:
    input_data = _load_object(input_path, label="data-accuracy input")
    report = _load_object(report_path, label="data-accuracy report")
    try:
        validate_data_accuracy(report_path)
    except ValueError as exc:
        raise WBLiveDataAcceptanceError(str(exc)) from exc

    if str(report.get("input_sha256") or "").lower() != _sha256(input_path).lower():
        raise WBLiveDataAcceptanceError("data-accuracy report is not bound to the supplied input")
    if str(input_data.get("wb_account_fingerprint") or "").lower() != account_fingerprint.lower():
        raise WBLiveDataAcceptanceError(
            "data-accuracy input WB account fingerprint does not match the live validated account"
        )
    seller_alias = str(input_data.get("seller_alias") or "").strip()
    if not seller_alias or "@" in seller_alias:
        raise WBLiveDataAcceptanceError("data-accuracy input must use a neutral seller_alias")
    periods = input_data.get("periods")
    if not isinstance(periods, list) or len(periods) < 3:
        raise WBLiveDataAcceptanceError("beta live data acceptance requires at least three periods")
    if report.get("period_count") != len(periods):
        raise WBLiveDataAcceptanceError("data-accuracy report period count does not match its input")
    counts = report.get("counts")
    if not isinstance(counts, dict):
        raise WBLiveDataAcceptanceError("data-accuracy report is missing result counts")
    if int(counts.get("missing") or 0) != 0 or int(counts.get("fail") or 0) != 0:
        raise WBLiveDataAcceptanceError("data-accuracy report contains missing or failed observations")
    return report


def validate_wb_live_data_evidence(
    path: Path,
    *,
    version: str,
    commit: str,
    environment: str,
) -> dict:
    report = _load_object(path, label="WB live data proof")
    if report.get("schema_version") != 1 or report.get("kind") != "wb_live_data":
        raise WBLiveDataAcceptanceError("WB live data proof has an invalid schema")
    if report.get("status") != "pass":
        raise WBLiveDataAcceptanceError("WB live data proof must report status=pass")
    if report.get("version") != version:
        raise WBLiveDataAcceptanceError("WB live data proof version mismatch")
    if str(report.get("commit") or "").lower() != commit.lower():
        raise WBLiveDataAcceptanceError("WB live data proof commit mismatch")
    if report.get("environment") != environment:
        raise WBLiveDataAcceptanceError("WB live data proof environment mismatch")
    _https_origin(str(report.get("public_origin") or ""))
    if SHA256_RE.fullmatch(str(report.get("wb_account_fingerprint") or "")) is None:
        raise WBLiveDataAcceptanceError("WB live data proof has an invalid account fingerprint")
    for field in ("accuracy_input_sha256", "data_accuracy_sha256"):
        if SHA256_RE.fullmatch(str(report.get(field) or "")) is None:
            raise WBLiveDataAcceptanceError(f"WB live data proof has invalid {field}")
    checks = report.get("checks")
    required = {
        "authenticated_account",
        "live_wb_credential_validated",
        "temporary_credential_removed",
        "account_fingerprint_matched",
        "data_accuracy_passed",
        "minimum_period_coverage",
    }
    if not isinstance(checks, dict) or any(checks.get(name) is not True for name in required):
        raise WBLiveDataAcceptanceError("WB live data proof is missing required passing checks")
    if not isinstance(report.get("period_count"), int) or report["period_count"] < 3:
        raise WBLiveDataAcceptanceError("WB live data proof must cover at least three periods")
    if not isinstance(report.get("metric_count"), int) or report["metric_count"] <= 0:
        raise WBLiveDataAcceptanceError("WB live data proof must cover data-accuracy metrics")
    return report


def _self_test() -> None:
    fingerprint = _account_fingerprint("seller-123", "0123456789abcdef0123456789abcdef")
    assert SHA256_RE.fullmatch(fingerprint)
    assert fingerprint == _account_fingerprint(
        "seller-123",
        "0123456789abcdef0123456789abcdef",
    )
    assert fingerprint != _account_fingerprint(
        "seller-124",
        "0123456789abcdef0123456789abcdef",
    )
    try:
        _https_origin("http://example.com")
    except WBLiveDataAcceptanceError:
        pass
    else:
        raise AssertionError("non-HTTPS origin unexpectedly accepted")
    print("[ok] WB live data acceptance self-test")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.getenv("WB_ACCEPTANCE_BASE_URL"))
    parser.add_argument("--email", default=os.getenv("WB_ACCEPTANCE_EMAIL"))
    parser.add_argument("--accuracy-input", type=Path)
    parser.add_argument("--data-accuracy", type=Path)
    parser.add_argument("--commit", default=os.getenv("RELEASE_SHA"))
    parser.add_argument("--environment", default=os.getenv("ACCEPTANCE_ENVIRONMENT"))
    parser.add_argument("--version-file", type=Path, default=Path("VERSION"))
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--fingerprint-only",
        action="store_true",
        help="Validate and remove a temporary WB credential, then print only its keyed account fingerprint",
    )
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return 0

    try:
        base_origin = _https_origin(str(args.base_url or ""))
        email = str(args.email or "").strip()
        password = str(os.getenv("WB_ACCEPTANCE_PASSWORD") or "")
        wb_token = str(os.getenv("WB_ACCEPTANCE_TOKEN") or "").strip()
        fingerprint_key = str(os.getenv("WB_ACCEPTANCE_FINGERPRINT_KEY") or "")
        commit = str(args.commit or "").strip()
        environment = str(args.environment or "").strip()
        if not email or not password:
            raise WBLiveDataAcceptanceError("acceptance account credentials are required")
        if not wb_token:
            raise WBLiveDataAcceptanceError("WB_ACCEPTANCE_TOKEN is required")
        if len(fingerprint_key.encode("utf-8")) < 16:
            raise WBLiveDataAcceptanceError("WB_ACCEPTANCE_FINGERPRINT_KEY must be at least 16 bytes")

        account_fingerprint = _probe_live_account(
            base_origin=base_origin,
            email=email,
            password=password,
            wb_token=wb_token,
            fingerprint_key=fingerprint_key,
        )
        if args.fingerprint_only:
            print(f"wb_account_fingerprint={account_fingerprint}")
            return 0

        if SHA40_RE.fullmatch(commit) is None:
            raise WBLiveDataAcceptanceError("release commit must be a full 40-character Git SHA")
        if not environment:
            raise WBLiveDataAcceptanceError("acceptance environment is required")
        if args.accuracy_input is None or args.data_accuracy is None or args.output is None:
            raise WBLiveDataAcceptanceError("accuracy input, data-accuracy report and output are required")
        version = args.version_file.read_text(encoding="utf-8").strip()
        if not version:
            raise WBLiveDataAcceptanceError("VERSION is empty")

        accuracy = _validate_accuracy_pair(
            args.accuracy_input,
            args.data_accuracy,
            account_fingerprint=account_fingerprint,
        )
        report = {
            "schema_version": 1,
            "kind": "wb_live_data",
            "status": "pass",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "version": version,
            "commit": commit.lower(),
            "environment": environment,
            "public_origin": base_origin,
            "wb_account_fingerprint": account_fingerprint,
            "accuracy_input_sha256": _sha256(args.accuracy_input),
            "data_accuracy_sha256": _sha256(args.data_accuracy),
            "period_count": int(accuracy["period_count"]),
            "metric_count": int(accuracy["metric_count"]),
            "checks": {
                "authenticated_account": True,
                "live_wb_credential_validated": True,
                "temporary_credential_removed": True,
                "account_fingerprint_matched": True,
                "data_accuracy_passed": True,
                "minimum_period_coverage": True,
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        validate_wb_live_data_evidence(
            args.output,
            version=version,
            commit=commit,
            environment=environment,
        )
        print(f"[ok] live WB/data-accuracy evidence: {args.output}")
        return 0
    except (OSError, UnicodeDecodeError, ValueError, WBLiveDataAcceptanceError) as exc:
        print(f"[failed] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
