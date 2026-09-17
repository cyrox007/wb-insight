#!/usr/bin/env python3
"""Run and validate production-like encrypted PostgreSQL backup/restore evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SHA40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
SAFE_REVISION_RE = re.compile(r"^[0-9a-fA-F]+$")


class BackupRestoreAcceptanceError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_restore_output(payload: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in payload.splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in {"restore_drill", "alembic_revision", "public_tables"}:
            values[key] = value
    if values.get("restore_drill") != "success":
        raise BackupRestoreAcceptanceError("restore drill did not report success")
    revision = values.get("alembic_revision", "")
    if not revision or SAFE_REVISION_RE.fullmatch(revision) is None:
        raise BackupRestoreAcceptanceError("restore drill returned invalid Alembic revision")
    try:
        table_count = int(values.get("public_tables", ""))
    except ValueError as exc:
        raise BackupRestoreAcceptanceError("restore drill returned invalid public table count") from exc
    if table_count <= 0:
        raise BackupRestoreAcceptanceError("restore drill restored no public tables")
    return {
        "alembic_revision": revision,
        "public_tables": str(table_count),
    }


def _write(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_backup_restore_evidence(
    path: Path,
    *,
    version: str,
    commit: str,
    environment: str,
) -> dict:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupRestoreAcceptanceError("backup_restore proof must be valid UTF-8 JSON") from exc
    if not isinstance(report, dict):
        raise BackupRestoreAcceptanceError("backup_restore proof must contain an object")
    if report.get("schema_version") != 1 or report.get("kind") != "backup_restore":
        raise BackupRestoreAcceptanceError("backup_restore proof has invalid schema")
    if report.get("status") != "pass":
        raise BackupRestoreAcceptanceError("backup_restore proof must report status=pass")
    if report.get("version") != version:
        raise BackupRestoreAcceptanceError("backup_restore proof version does not match release VERSION")
    if str(report.get("commit") or "").lower() != commit.lower():
        raise BackupRestoreAcceptanceError("backup_restore proof commit does not match release commit")
    if report.get("environment") != environment:
        raise BackupRestoreAcceptanceError("backup_restore proof environment does not match release environment")
    for field in ("backup_sha256", "checksum_file_sha256"):
        if SHA256_RE.fullmatch(str(report.get(field) or "")) is None:
            raise BackupRestoreAcceptanceError(f"backup_restore proof has invalid {field}")
    if report.get("checksum_verified") is not True:
        raise BackupRestoreAcceptanceError("backup_restore proof must verify the backup checksum")
    if report.get("restore_completed") is not True:
        raise BackupRestoreAcceptanceError("backup_restore proof must prove isolated restore completion")
    if report.get("temporary_database_cleaned") is not True:
        raise BackupRestoreAcceptanceError("backup_restore proof must prove temporary database cleanup")
    revision = str(report.get("alembic_revision") or "")
    if SAFE_REVISION_RE.fullmatch(revision) is None:
        raise BackupRestoreAcceptanceError("backup_restore proof has invalid Alembic revision")
    tables = report.get("public_tables")
    if not isinstance(tables, int) or tables <= 0:
        raise BackupRestoreAcceptanceError("backup_restore proof has invalid public table count")
    return report


def _self_test() -> None:
    parsed = _parse_restore_output(
        "restore_drill=success\ndatabase=ignored\nalembic_revision=abcdef123456\npublic_tables=42\n"
    )
    assert parsed == {"alembic_revision": "abcdef123456", "public_tables": "42"}
    try:
        _parse_restore_output("restore_drill=success\nalembic_revision=abcdef\npublic_tables=0\n")
    except BackupRestoreAcceptanceError:
        pass
    else:
        raise AssertionError("zero-table restore unexpectedly passed")
    print("[ok] backup restore acceptance self-test")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--project-dir", type=Path, default=Path(os.getenv("PROJECT_DIR", "/home/projects/wb")))
    parser.add_argument("--version-file", type=Path, default=Path("VERSION"))
    parser.add_argument("--commit", default=os.getenv("RELEASE_SHA"))
    parser.add_argument("--environment", default=os.getenv("ACCEPTANCE_ENVIRONMENT"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return 0
    if args.backup is None or args.output is None:
        raise BackupRestoreAcceptanceError("--backup and --output are required")
    commit = str(args.commit or "").strip()
    environment = str(args.environment or "").strip()
    if SHA40_RE.fullmatch(commit) is None:
        raise BackupRestoreAcceptanceError("--commit or RELEASE_SHA must be a full 40-character Git SHA")
    if not environment:
        raise BackupRestoreAcceptanceError("--environment or ACCEPTANCE_ENVIRONMENT is required")
    try:
        version = args.version_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise BackupRestoreAcceptanceError("unable to read VERSION") from exc
    if not version:
        raise BackupRestoreAcceptanceError("VERSION is empty")

    backup = args.backup.resolve()
    checksum = Path(str(backup) + ".sha256")
    if not backup.is_file() or not checksum.is_file():
        raise BackupRestoreAcceptanceError("encrypted backup and adjacent .sha256 file are required")
    project = args.project_dir.resolve()
    drill = project / "ops" / "postgres_restore_drill.sh"
    if not drill.is_file():
        raise BackupRestoreAcceptanceError("postgres_restore_drill.sh is missing")

    completed = subprocess.run(
        ["bash", str(drill), str(backup)],
        cwd=str(project),
        check=False,
        capture_output=True,
        text=True,
        timeout=900,
    )
    if completed.returncode != 0:
        raise BackupRestoreAcceptanceError("isolated restore drill failed")
    parsed = _parse_restore_output(completed.stdout)

    # postgres_restore_drill.sh installs an EXIT trap that always drops the temporary DB.
    # The acceptance report intentionally records only the successful contract, never DB names.
    report = {
        "schema_version": 1,
        "kind": "backup_restore",
        "status": "pass",
        "version": version,
        "commit": commit.lower(),
        "environment": environment,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "backup_file": backup.name,
        "backup_size_bytes": backup.stat().st_size,
        "backup_sha256": _sha256(backup),
        "checksum_file": checksum.name,
        "checksum_file_sha256": _sha256(checksum),
        "checksum_verified": True,
        "restore_completed": True,
        "temporary_database_cleaned": True,
        "alembic_revision": parsed["alembic_revision"],
        "public_tables": int(parsed["public_tables"]),
    }
    _write(args.output, report)
    validate_backup_restore_evidence(
        args.output,
        version=version,
        commit=commit,
        environment=environment,
    )
    print(f"[ok] structured backup/restore evidence: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BackupRestoreAcceptanceError as exc:
        print(f"[failed] {exc}", file=sys.stderr)
        raise SystemExit(1)
