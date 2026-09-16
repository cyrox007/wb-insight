#!/usr/bin/env python3
"""Scan WB Insight release surfaces for configured secret leakage.

The scanner compares configured secret values with the current checkout, reachable
Git blobs, built frontend assets and bounded systemd journal output. Secret values,
matching lines and journal contents are never printed or written to the report.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterable


DEFAULT_SECRET_NAMES = {
    "DB_PASSWORD",
    "API_TOKEN_ENCRYPTION_KEY",
    "JWT_SECRET_KEY",
    "LEGAL_EVIDENCE_HMAC_KEY",
    "SMTP_PASSWORD",
    "WB_SERVICE_SECRET",
    "SBER_PASSWORD",
    "OPS_ALERT_WEBHOOK_URL",
}

DEFAULT_SECRET_FILE_ENVS = {"BACKUP_ENCRYPTION_PASSPHRASE_FILE"}
DEFAULT_JOURNAL_UNITS = ("wb-backend", "wb-celery", "wb-celery-beat")
PLACEHOLDER_PREFIXES = ("replace-with-", "example-", "changeme", "change-me")
JWT_RE = re.compile(rb"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")


class ReviewError(RuntimeError):
    pass


def _run(argv: list[str], *, cwd: Path | None = None, timeout: int = 60) -> bytes:
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            check=False,
            capture_output=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReviewError(f"command failed to start: {argv[0]}") from exc
    if completed.returncode != 0:
        raise ReviewError(f"command failed: {argv[0]}")
    return completed.stdout


def _parse_env_file(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    if not path.is_file():
        raise ReviewError("configured env file does not exist")
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith(("'", '"')) and len(value) >= 2 and value[-1] == value[0]:
            value = value[1:-1]
        values[key] = value
    return values


def _usable_secret(value: str) -> bool:
    normalized = value.strip()
    if len(normalized) < 12:
        return False
    lowered = normalized.lower()
    return not any(lowered.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def _configured_secrets(
    *,
    env_file: Path | None,
    secret_names: set[str],
    secret_file_envs: set[str],
) -> dict[str, bytes]:
    file_values = _parse_env_file(env_file)
    result: dict[str, bytes] = {}

    for name in sorted(secret_names):
        value = os.getenv(name)
        if value is None:
            value = file_values.get(name)
        if value is not None and _usable_secret(value):
            result[name] = value.encode("utf-8")

    for env_name in sorted(secret_file_envs):
        path_value = os.getenv(env_name) or file_values.get(env_name)
        if not path_value:
            continue
        secret_path = Path(path_value)
        try:
            raw = secret_path.read_bytes().strip()
        except OSError as exc:
            raise ReviewError(f"secret file referenced by {env_name} is unreadable") from exc
        if len(raw) >= 12:
            result[env_name] = raw

    return result


def _scan_payload(
    payload: bytes,
    secrets: dict[str, bytes],
    *,
    scope: str,
    detect_jwt: bool,
    findings: dict[str, set[str]],
) -> None:
    for name, secret in secrets.items():
        if secret and secret in payload:
            findings.setdefault(name, set()).add(scope)
    if detect_jwt and JWT_RE.search(payload):
        findings.setdefault("dynamic_jwt_pattern", set()).add(scope)


def _iter_files(root: Path, *, max_file_bytes: int) -> Iterable[Path]:
    if root.is_file():
        if root.stat().st_size <= max_file_bytes:
            yield root
        return
    if not root.is_dir():
        return
    for path in root.rglob("*"):
        try:
            if path.is_file() and not path.is_symlink() and path.stat().st_size <= max_file_bytes:
                yield path
        except OSError:
            continue


def _scan_files(
    paths: Iterable[Path],
    secrets: dict[str, bytes],
    *,
    scope: str,
    detect_jwt: bool,
    findings: dict[str, set[str]],
) -> tuple[int, int]:
    files = 0
    total_bytes = 0
    for path in paths:
        try:
            payload = path.read_bytes()
        except OSError:
            continue
        files += 1
        total_bytes += len(payload)
        _scan_payload(
            payload,
            secrets,
            scope=scope,
            detect_jwt=detect_jwt,
            findings=findings,
        )
    return files, total_bytes


def _tracked_files(project: Path, *, max_file_bytes: int) -> list[Path]:
    output = _run(["git", "ls-files", "-z"], cwd=project)
    result: list[Path] = []
    for raw in output.split(b"\0"):
        if not raw:
            continue
        try:
            relative = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        path = project / relative
        try:
            if path.is_file() and path.stat().st_size <= max_file_bytes:
                result.append(path)
        except OSError:
            continue
    return result


def _scan_git_history(
    project: Path,
    secrets: dict[str, bytes],
    *,
    max_blob_bytes: int,
    findings: dict[str, set[str]],
) -> tuple[int, int]:
    objects = _run(["git", "rev-list", "--objects", "--all"], cwd=project, timeout=120)
    seen: set[str] = set()
    scanned = 0
    total_bytes = 0
    for raw_line in objects.splitlines():
        if not raw_line:
            continue
        sha = raw_line.split(maxsplit=1)[0].decode("ascii", errors="ignore")
        if len(sha) != 40 or sha in seen:
            continue
        seen.add(sha)
        try:
            object_type = _run(["git", "cat-file", "-t", sha], cwd=project, timeout=10).strip()
            if object_type != b"blob":
                continue
            size_raw = _run(["git", "cat-file", "-s", sha], cwd=project, timeout=10).strip()
            size = int(size_raw)
            if size > max_blob_bytes:
                continue
            payload = _run(["git", "cat-file", "blob", sha], cwd=project, timeout=20)
        except (ReviewError, ValueError):
            continue
        scanned += 1
        total_bytes += len(payload)
        _scan_payload(
            payload,
            secrets,
            scope="git_history",
            detect_jwt=False,
            findings=findings,
        )
    return scanned, total_bytes


def _scan_journal(
    secrets: dict[str, bytes],
    *,
    units: tuple[str, ...],
    lines: int,
    since: str | None,
    findings: dict[str, set[str]],
) -> int:
    argv = ["journalctl", "--no-pager", "--output=cat", "-n", str(lines)]
    if since:
        argv.extend(["--since", since])
    for unit in units:
        argv.extend(["-u", unit])
    payload = _run(argv, timeout=60)
    _scan_payload(
        payload,
        secrets,
        scope="systemd_journal",
        detect_jwt=True,
        findings=findings,
    )
    return len(payload)


def _git_identity(project: Path) -> tuple[str, str]:
    commit = _run(["git", "rev-parse", "HEAD"], cwd=project).decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ReviewError("Git HEAD is not a full commit SHA")
    version_path = project / "VERSION"
    if not version_path.is_file():
        raise ReviewError("VERSION is missing")
    version = version_path.read_text(encoding="utf-8").strip()
    if not version:
        raise ReviewError("VERSION is empty")
    return commit, version


def _write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _self_test() -> None:
    secret = b"self-test-secret-value-123456789"
    findings: dict[str, set[str]] = {}
    _scan_payload(
        b"safe prefix " + secret + b" safe suffix",
        {"TEST_SECRET": secret},
        scope="fixture",
        detect_jwt=False,
        findings=findings,
    )
    assert findings == {"TEST_SECRET": {"fixture"}}

    jwt_findings: dict[str, set[str]] = {}
    _scan_payload(
        b"eyJhbGciOiJIUzI1NiJ9.abcdefghijklmno.pqrstuvwxyz12345",
        {},
        scope="journal",
        detect_jwt=True,
        findings=jwt_findings,
    )
    assert "dynamic_jwt_pattern" in jwt_findings

    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "report.json"
        report = {"secret_names_checked": ["TEST_SECRET"], "findings_count": 0}
        _write_report(path, report)
        serialized = path.read_bytes()
        assert secret not in serialized
    print("[ok] secrets review self-test")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path(os.getenv("PROJECT_DIR", "/home/projects/wb")))
    parser.add_argument("--environment", default=os.getenv("ACCEPTANCE_ENVIRONMENT"))
    parser.add_argument("--env-file", type=Path, default=Path(os.environ["SECRETS_REVIEW_ENV_FILE"]) if os.getenv("SECRETS_REVIEW_ENV_FILE") else None)
    parser.add_argument("--secret-name", action="append", default=[])
    parser.add_argument("--secret-file-env", action="append", default=[])
    parser.add_argument("--scan-log", type=Path, action="append", default=[])
    parser.add_argument("--journal-unit", action="append", default=[])
    parser.add_argument("--journal-lines", type=int, default=int(os.getenv("SECRETS_REVIEW_JOURNAL_LINES", "20000")))
    parser.add_argument("--journal-since", default=os.getenv("SECRETS_REVIEW_JOURNAL_SINCE"))
    parser.add_argument("--max-file-bytes", type=int, default=5 * 1024 * 1024)
    parser.add_argument("--skip-git-history", action="store_true")
    parser.add_argument("--skip-journal", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return 0
    if not args.environment or not args.environment.strip():
        raise ReviewError("--environment or ACCEPTANCE_ENVIRONMENT is required")
    if args.output is None:
        raise ReviewError("--output is required")
    if args.journal_lines <= 0 or args.journal_lines > 200000:
        raise ReviewError("journal line limit must be between 1 and 200000")
    if args.max_file_bytes < 1024 or args.max_file_bytes > 100 * 1024 * 1024:
        raise ReviewError("max file size is outside the supported range")

    project = args.project_dir.resolve()
    if not (project / ".git").is_dir():
        raise ReviewError("project directory is not a Git checkout")

    commit, version = _git_identity(project)
    secret_names = DEFAULT_SECRET_NAMES | {name.strip() for name in args.secret_name if name.strip()}
    secret_file_envs = DEFAULT_SECRET_FILE_ENVS | {
        name.strip() for name in args.secret_file_env if name.strip()
    }
    secrets = _configured_secrets(
        env_file=args.env_file,
        secret_names=secret_names,
        secret_file_envs=secret_file_envs,
    )
    if not secrets:
        raise ReviewError("no configured secret values were available for review")

    findings: dict[str, set[str]] = {}
    tracked_files, tracked_bytes = _scan_files(
        _tracked_files(project, max_file_bytes=args.max_file_bytes),
        secrets,
        scope="git_worktree",
        detect_jwt=False,
        findings=findings,
    )

    history_blobs = history_bytes = 0
    if not args.skip_git_history:
        history_blobs, history_bytes = _scan_git_history(
            project,
            secrets,
            max_blob_bytes=args.max_file_bytes,
            findings=findings,
        )

    frontend_files, frontend_bytes = _scan_files(
        _iter_files(project / "frontend" / "dist", max_file_bytes=args.max_file_bytes),
        secrets,
        scope="frontend_dist",
        detect_jwt=True,
        findings=findings,
    )
    if frontend_files <= 0:
        raise ReviewError("frontend/dist is missing or empty")

    extra_log_files = extra_log_bytes = 0
    for raw_path in args.scan_log:
        files, size = _scan_files(
            _iter_files(raw_path.resolve(), max_file_bytes=args.max_file_bytes),
            secrets,
            scope="extra_logs",
            detect_jwt=True,
            findings=findings,
        )
        extra_log_files += files
        extra_log_bytes += size

    journal_bytes = 0
    journal_checked = not args.skip_journal
    if journal_checked:
        units = tuple(args.journal_unit) or DEFAULT_JOURNAL_UNITS
        journal_bytes = _scan_journal(
            secrets,
            units=units,
            lines=args.journal_lines,
            since=args.journal_since,
            findings=findings,
        )

    normalized_findings = [
        {"secret_name": name, "scopes": sorted(scopes)}
        for name, scopes in sorted(findings.items())
    ]
    report = {
        "schema_version": 1,
        "kind": "secrets_review",
        "status": "pass" if not normalized_findings else "fail",
        "version": version,
        "commit": commit,
        "environment": args.environment.strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "secret_names_checked": sorted(secrets),
        "findings_count": len(normalized_findings),
        "findings": normalized_findings,
        "git_history_checked": not args.skip_git_history,
        "journal_checked": journal_checked,
        "scan_stats": {
            "git_worktree_files": tracked_files,
            "git_worktree_bytes": tracked_bytes,
            "git_history_blobs": history_blobs,
            "git_history_bytes": history_bytes,
            "frontend_files": frontend_files,
            "frontend_bytes": frontend_bytes,
            "extra_log_files": extra_log_files,
            "extra_log_bytes": extra_log_bytes,
            "journal_bytes": journal_bytes,
        },
    }
    _write_report(args.output, report)
    if normalized_findings:
        print(f"[failed] secret review found {len(normalized_findings)} leak category/categories", file=sys.stderr)
        return 1
    print(f"[ok] structured secrets review evidence: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ReviewError as exc:
        print(f"[failed] {exc}", file=sys.stderr)
        raise SystemExit(1)
