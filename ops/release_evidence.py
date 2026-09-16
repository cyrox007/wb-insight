#!/usr/bin/env python3
"""Build and validate a WB Insight release-evidence manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


BETA_REQUIRED = {
    "ci",
    "deployment",
    "core_smoke",
    "account_lifecycle",
    "ux_smoke",
    "secrets_review",
    "data_accuracy",
}

REQUIRED = {
    "beta": BETA_REQUIRED,
    "rc": BETA_REQUIRED
    | {
        "wb_full_sync",
        "sber_payment",
        "operations",
        "backup_restore",
        "legal",
    },
    "stable": BETA_REQUIRED
    | {
        "wb_full_sync",
        "sber_payment",
        "operations",
        "backup_restore",
        "legal",
        "rc_signoff",
    },
}

KNOWN_ARTIFACT_KINDS = set().union(*REQUIRED.values())
SHA40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
VERSION_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<stage>alpha|beta|rc)\.(?P<iteration>[1-9]\d*))?$"
)

DEPLOYMENT_REQUIRED_CHECKS = {
    "git_clean",
    "target_branch_exact_head",
    "immutable_release_venv",
    "python_3_12",
    "supported_node",
    "systemd_services_active_enabled",
    "celery_worker_ping",
    "alembic_at_head",
    "nginx_config_valid",
    "local_readiness",
    "public_https_readiness",
    "frontend_bundle_published",
    "rollback_proof_bound",
}

CORE_SMOKE_REQUIRED_CHECKS = {
    "public_health_legal",
    "disposable_registration",
    "email_verification",
    "demo_activation",
    "legal_consent_evidence",
    "disposable_refresh_restore",
    "deactivation",
    "inactive_login_rejected",
    "authenticated_profile",
    "authenticated_refresh_restore",
    "dashboard_contract",
    "audit_correlation",
    "logout_session_revoke",
}

ACCOUNT_LIFECYCLE_REQUIRED_CHECKS = {
    "email_verification",
    "password_reset",
    "deactivation",
    "inactive_login_rejected",
    "authenticated_refresh_restore",
    "logout_session_revoke",
}

SECRETS_REVIEW_CORE_NAMES = {
    "DB_PASSWORD",
    "API_TOKEN_ENCRYPTION_KEY",
    "JWT_SECRET_KEY",
    "LEGAL_EVIDENCE_HMAC_KEY",
    "WB_SERVICE_SECRET",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_artifact(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError("artifact must use kind=path format")
    kind, raw_path = value.split("=", 1)
    kind = kind.strip()
    path = Path(raw_path.strip())
    if not kind or not raw_path.strip():
        raise ValueError("artifact kind and path must be non-empty")
    if kind not in KNOWN_ARTIFACT_KINDS:
        raise ValueError(f"unknown artifact kind: {kind}")
    return kind, path


def validate_version_for_stage(version: str, stage: str) -> None:
    match = VERSION_RE.fullmatch(version)
    if match is None:
        raise ValueError(f"VERSION is not a supported release version: {version}")

    prerelease_stage = match.group("stage")
    if stage == "stable":
        if prerelease_stage is not None:
            raise ValueError("stable evidence requires a VERSION without prerelease suffix")
        return
    if prerelease_stage != stage:
        raise ValueError(
            f"{stage} evidence requires a VERSION with -{stage}.N suffix"
        )


def load_json_object(path: Path, *, artifact_kind: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{artifact_kind} artifact must be valid UTF-8 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{artifact_kind} artifact must contain a JSON object")
    return value


def validate_data_accuracy(path: Path) -> None:
    report = load_json_object(path, artifact_kind="data_accuracy")
    if report.get("schema_version") != 1:
        raise ValueError("data_accuracy artifact must use schema_version=1")
    if report.get("status") != "pass":
        raise ValueError("data_accuracy artifact must report status=pass")
    if not isinstance(report.get("period_count"), int) or report["period_count"] <= 0:
        raise ValueError("data_accuracy artifact must contain at least one period")
    if not isinstance(report.get("metric_count"), int) or report["metric_count"] <= 0:
        raise ValueError("data_accuracy artifact must contain at least one metric")
    for field in ("input_sha256", "policy_sha256"):
        value = str(report.get(field) or "")
        if SHA256_RE.fullmatch(value) is None:
            raise ValueError(f"data_accuracy artifact must contain a valid {field}")


def _validate_https_origin(value: object, *, artifact_kind: str) -> None:
    parsed = urlparse(str(value or ""))
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError(f"{artifact_kind} artifact must bind a public HTTPS origin")


def _require_true_checks(report: dict[str, Any], names: set[str], *, artifact_kind: str) -> None:
    checks = report.get("checks")
    if not isinstance(checks, dict):
        raise ValueError(f"{artifact_kind} artifact must contain a checks object")
    missing = sorted(name for name in names if checks.get(name) is not True)
    if missing:
        raise ValueError(
            f"{artifact_kind} artifact is missing passing checks: {', '.join(missing)}"
        )


def validate_deployment_evidence(
    path: Path,
    *,
    version: str,
    commit: str,
    environment: str,
) -> None:
    report = load_json_object(path, artifact_kind="deployment")
    if report.get("schema_version") != 1 or report.get("kind") != "deployment":
        raise ValueError("deployment artifact must use schema_version=1 and kind=deployment")
    if report.get("status") != "pass":
        raise ValueError("deployment artifact must report status=pass")
    if report.get("version") != version:
        raise ValueError("deployment artifact version does not match release VERSION")
    if str(report.get("commit") or "").lower() != commit.lower():
        raise ValueError("deployment artifact commit does not match release commit")
    if report.get("environment") != environment:
        raise ValueError("deployment artifact environment does not match manifest environment")
    _validate_https_origin(report.get("public_origin"), artifact_kind="deployment")
    _require_true_checks(report, DEPLOYMENT_REQUIRED_CHECKS, artifact_kind="deployment")
    rollback_hash = str(report.get("rollback_proof_sha256") or "")
    if SHA256_RE.fullmatch(rollback_hash) is None:
        raise ValueError("deployment artifact must bind a valid rollback proof SHA-256")

    runtime = report.get("runtime")
    if not isinstance(runtime, dict):
        raise ValueError("deployment artifact must contain runtime metadata")
    if not str(runtime.get("python") or "").startswith("3.12."):
        raise ValueError("deployment artifact must prove Python 3.12 runtime")
    if not str(runtime.get("venv_release") or "").startswith("venv.release."):
        raise ValueError("deployment artifact must prove immutable release venv")
    revisions = runtime.get("alembic_revisions")
    if not isinstance(revisions, list) or not revisions:
        raise ValueError("deployment artifact must contain Alembic revision evidence")


def validate_release_smoke_evidence(
    path: Path,
    *,
    version: str,
    artifact_kind: str,
) -> None:
    report = load_json_object(path, artifact_kind=artifact_kind)
    if report.get("schema_version") != 1 or report.get("kind") != "release_smoke":
        raise ValueError(
            f"{artifact_kind} artifact must use schema_version=1 and kind=release_smoke"
        )
    if report.get("status") != "pass":
        raise ValueError(f"{artifact_kind} artifact must report status=pass")
    if report.get("version") != version:
        raise ValueError(f"{artifact_kind} artifact version does not match release VERSION")
    _validate_https_origin(report.get("base_origin"), artifact_kind=artifact_kind)
    required = (
        CORE_SMOKE_REQUIRED_CHECKS
        if artifact_kind == "core_smoke"
        else ACCOUNT_LIFECYCLE_REQUIRED_CHECKS
    )
    _require_true_checks(report, required, artifact_kind=artifact_kind)


def validate_secrets_review_evidence(
    path: Path,
    *,
    version: str,
    commit: str,
    environment: str,
) -> None:
    report = load_json_object(path, artifact_kind="secrets_review")
    if report.get("schema_version") != 1 or report.get("kind") != "secrets_review":
        raise ValueError(
            "secrets_review artifact must use schema_version=1 and kind=secrets_review"
        )
    if report.get("status") != "pass":
        raise ValueError("secrets_review artifact must report status=pass")
    if report.get("version") != version:
        raise ValueError("secrets_review artifact version does not match release VERSION")
    if str(report.get("commit") or "").lower() != commit.lower():
        raise ValueError("secrets_review artifact commit does not match release commit")
    if report.get("environment") != environment:
        raise ValueError("secrets_review artifact environment does not match manifest environment")
    if report.get("findings_count") != 0:
        raise ValueError("secrets_review artifact contains leak findings")
    findings = report.get("findings")
    if not isinstance(findings, list) or findings:
        raise ValueError("secrets_review artifact findings must be an empty list")
    if report.get("git_history_checked") is not True:
        raise ValueError("secrets_review artifact must scan reachable Git history")
    if report.get("journal_checked") is not True:
        raise ValueError("secrets_review artifact must scan runtime systemd journal")

    checked = report.get("secret_names_checked")
    if not isinstance(checked, list) or not checked:
        raise ValueError("secrets_review artifact must list configured secret names checked")
    missing_names = sorted(SECRETS_REVIEW_CORE_NAMES - {str(item) for item in checked})
    if missing_names:
        raise ValueError(
            "secrets_review artifact did not check required production secrets: "
            + ", ".join(missing_names)
        )

    stats = report.get("scan_stats")
    if not isinstance(stats, dict):
        raise ValueError("secrets_review artifact must contain scan_stats")
    for field in ("git_worktree_files", "git_history_blobs", "frontend_files"):
        value = stats.get(field)
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"secrets_review artifact must scan at least one {field}")
    journal_bytes = stats.get("journal_bytes")
    if not isinstance(journal_bytes, int) or journal_bytes < 0:
        raise ValueError("secrets_review artifact has invalid journal_bytes")


def validate_artifact(
    kind: str,
    path: Path,
    *,
    structured_runtime_evidence: bool,
    version: str,
    commit: str,
    environment: str,
) -> int:
    if not path.is_file():
        raise ValueError(f"artifact does not exist: {path}")
    size = path.stat().st_size
    if size <= 0:
        raise ValueError(f"artifact must not be empty: {path}")
    if kind == "data_accuracy":
        validate_data_accuracy(path)
    elif structured_runtime_evidence and kind == "deployment":
        validate_deployment_evidence(
            path,
            version=version,
            commit=commit,
            environment=environment,
        )
    elif structured_runtime_evidence and kind in {"core_smoke", "account_lifecycle"}:
        validate_release_smoke_evidence(
            path,
            version=version,
            artifact_kind=kind,
        )
    elif structured_runtime_evidence and kind == "secrets_review":
        validate_secrets_review_evidence(
            path,
            version=version,
            commit=commit,
            environment=environment,
        )
    return size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=sorted(REQUIRED), required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--version-file", type=Path, default=Path("VERSION"))
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument(
        "--require-structured-runtime-evidence",
        action="store_true",
        help=(
            "Require deployment/core_smoke/account_lifecycle/secrets_review JSON evidence "
            "bound to the exact release version, commit and HTTPS environment"
        ),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    environment = args.environment.strip()
    commit = args.commit.strip()
    if not environment:
        print("release_evidence_error=environment must be non-empty", file=sys.stderr)
        return 2
    if SHA40_RE.fullmatch(commit) is None:
        print("release_evidence_error=commit must be a full 40-character Git SHA", file=sys.stderr)
        return 2

    try:
        version = args.version_file.read_text(encoding="utf-8").strip()
        validate_version_for_stage(version, args.stage)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"release_evidence_error={exc}", file=sys.stderr)
        return 2
    if not version:
        print("release_evidence_error=VERSION is empty", file=sys.stderr)
        return 2

    artifacts = []
    kinds: set[str] = set()
    try:
        for raw in args.artifact:
            kind, path = parse_artifact(raw)
            if kind in kinds:
                raise ValueError(f"duplicate artifact kind: {kind}")
            size = validate_artifact(
                kind,
                path,
                structured_runtime_evidence=args.require_structured_runtime_evidence,
                version=version,
                commit=commit,
                environment=environment,
            )
            kinds.add(kind)
            artifacts.append(
                {
                    "kind": kind,
                    "file": path.name,
                    "size_bytes": size,
                    "sha256": sha256(path),
                }
            )
    except (OSError, ValueError) as exc:
        print(f"release_evidence_error={exc}", file=sys.stderr)
        return 2

    missing = sorted(REQUIRED[args.stage] - kinds)
    report = {
        "schema_version": 2,
        "stage": args.stage,
        "status": "complete" if not missing else "incomplete",
        "version": version,
        "commit": commit.lower(),
        "environment": environment,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "structured_runtime_evidence_required": args.require_structured_runtime_evidence,
        "required_artifact_kinds": sorted(REQUIRED[args.stage]),
        "missing_artifact_kinds": missing,
        "artifacts": sorted(artifacts, key=lambda item: item["kind"]),
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
