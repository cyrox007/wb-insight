#!/usr/bin/env python3
"""Prove that an encrypted WB Insight backup upgrades cleanly in an isolated database.

The source database is never modified. Credentials and decrypted backup bytes are not
written to evidence. The temporary restore database is dropped on every exit path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory


SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
REVISION_RE = re.compile(r"\b[0-9a-f]{8,40}\b", re.IGNORECASE)


class UpgradeAcceptanceError(RuntimeError):
    pass


def _run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 180,
) -> str:
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpgradeAcceptanceError(f"command failed to start: {argv[0]}") from exc
    if completed.returncode != 0:
        # stdout/stderr can contain DB names or operational data; do not surface it.
        raise UpgradeAcceptanceError(f"command failed: {argv[0]}")
    return completed.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_env_file(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    if not path.is_file():
        raise UpgradeAcceptanceError("configured env file does not exist")
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith(("'", '"')) and len(value) >= 2 and value[-1] == value[0]:
            value = value[1:-1]
        result[key] = value
    return result


def _runtime_env(env_file: Path | None) -> dict[str, str]:
    result = os.environ.copy()
    for key, value in _parse_env_file(env_file).items():
        result.setdefault(key, value)
    required = ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME")
    missing = [key for key in required if not str(result.get(key) or "").strip()]
    if missing:
        raise UpgradeAcceptanceError("database configuration is incomplete: " + ", ".join(missing))
    result.setdefault("DB_PORT", "5432")
    result["PGPASSWORD"] = result["DB_PASSWORD"]
    return result


def _revisions(output: str) -> list[str]:
    return sorted({value.lower() for value in REVISION_RE.findall(output)})


def _write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _require_commands() -> None:
    for name in ("openssl", "createdb", "dropdb", "pg_restore", "psql"):
        if shutil.which(name) is None:
            raise UpgradeAcceptanceError(f"required command is missing: {name}")


def _self_test() -> None:
    assert _revisions("abc12345 (head)\nABC12345") == ["abc12345"]
    assert SHA40_RE.fullmatch("0123456789abcdef0123456789abcdef01234567")
    assert not SHA40_RE.fullmatch("short")
    print("[ok] database upgrade acceptance self-test")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path(os.getenv("PROJECT_DIR", "/home/projects/wb")))
    parser.add_argument("--environment", default=os.getenv("ACCEPTANCE_ENVIRONMENT"))
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--env-file", type=Path, default=Path(os.environ["DB_UPGRADE_ENV_FILE"]) if os.getenv("DB_UPGRADE_ENV_FILE") else None)
    parser.add_argument(
        "--passphrase-file",
        type=Path,
        default=(
            Path(os.environ["BACKUP_ENCRYPTION_PASSPHRASE_FILE"])
            if os.getenv("BACKUP_ENCRYPTION_PASSPHRASE_FILE")
            else None
        ),
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return 0
    if not args.environment or not args.environment.strip():
        raise UpgradeAcceptanceError("--environment or ACCEPTANCE_ENVIRONMENT is required")
    if args.backup is None:
        raise UpgradeAcceptanceError("--backup is required")
    if args.passphrase_file is None:
        raise UpgradeAcceptanceError("--passphrase-file or BACKUP_ENCRYPTION_PASSPHRASE_FILE is required")
    if args.output is None:
        raise UpgradeAcceptanceError("--output is required")

    _require_commands()
    project = args.project_dir.resolve()
    backend = project / "backend"
    version_file = project / "VERSION"
    venv_python = backend / "venv" / "bin" / "python"
    backup = args.backup.resolve()
    checksum = Path(f"{backup}.sha256")
    passphrase = args.passphrase_file.resolve()

    if not (project / ".git").is_dir() or not version_file.is_file():
        raise UpgradeAcceptanceError("project checkout is incomplete")
    if not venv_python.is_file():
        raise UpgradeAcceptanceError("active backend Python runtime is missing")
    if not backup.is_file() or backup.stat().st_size <= 0:
        raise UpgradeAcceptanceError("encrypted backup is missing or empty")
    if not checksum.is_file() or checksum.stat().st_size <= 0:
        raise UpgradeAcceptanceError("backup checksum is missing or empty")
    if not passphrase.is_file() or passphrase.stat().st_size <= 0:
        raise UpgradeAcceptanceError("backup passphrase file is missing or empty")

    version = version_file.read_text(encoding="utf-8").strip()
    commit = _run(["git", "rev-parse", "HEAD"], cwd=project)
    if SHA40_RE.fullmatch(commit) is None:
        raise UpgradeAcceptanceError("Git HEAD is not a full commit SHA")

    env = _runtime_env(args.env_file)
    host = env["DB_HOST"]
    port = env["DB_PORT"]
    user = env["DB_USER"]
    source_db = env["DB_NAME"]
    drill_db = f"wb_upgrade_accept_{secrets.token_hex(6)}"
    if drill_db == source_db:
        raise UpgradeAcceptanceError("isolated database name collision")

    checks: list[str] = []
    report = {
        "schema_version": 1,
        "kind": "database_upgrade",
        "status": "fail",
        "environment": args.environment.strip(),
        "version": version,
        "commit": commit,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }

    created = False
    try:
        # Verify the producer checksum before decrypting. The command runs in the
        # backup directory so checksum files with basenames remain portable.
        _run(["sha256sum", "--check", checksum.name], cwd=backup.parent, env=env)
        checks.append("backup_integrity")
        backup_hash = _sha256(backup)

        with TemporaryDirectory(prefix="wb-db-upgrade-") as tmp:
            decrypted = Path(tmp) / "source.dump"
            _run(
                [
                    "openssl",
                    "enc",
                    "-d",
                    "-aes-256-cbc",
                    "-pbkdf2",
                    "-iter",
                    "200000",
                    "-pass",
                    f"file:{passphrase}",
                    "-in",
                    str(backup),
                    "-out",
                    str(decrypted),
                ],
                env=env,
            )

            _run(["createdb", "--host", host, "--port", port, "--username", user, drill_db], env=env)
            created = True
            _run(
                [
                    "pg_restore",
                    "--no-owner",
                    "--no-privileges",
                    "--host",
                    host,
                    "--port",
                    port,
                    "--username",
                    user,
                    "--dbname",
                    drill_db,
                    str(decrypted),
                ],
                env=env,
                timeout=600,
            )
            checks.append("isolated_restore")

            psql = ["psql", "--host", host, "--port", port, "--username", user, "--dbname", drill_db, "--tuples-only", "--no-align", "--set", "ON_ERROR_STOP=1"]
            source_revision_raw = _run([*psql, "--command", "SELECT version_num FROM alembic_version ORDER BY version_num;"], env=env)
            source_revisions = [line.strip() for line in source_revision_raw.splitlines() if line.strip()]
            table_count_before = int(
                _run(
                    [*psql, "--command", "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"],
                    env=env,
                )
            )
            if not source_revisions or table_count_before <= 0:
                raise UpgradeAcceptanceError("restored database failed baseline validation")

            upgrade_env = env.copy()
            upgrade_env["DB_NAME"] = drill_db
            upgrade_env.setdefault("APP_ENV", "development")
            _run([str(venv_python), "-m", "alembic", "upgrade", "head"], cwd=backend, env=upgrade_env, timeout=600)
            checks.append("alembic_upgrade")

            current = _run([str(venv_python), "-m", "alembic", "current"], cwd=backend, env=upgrade_env)
            heads = _run([str(venv_python), "-m", "alembic", "heads"], cwd=backend, env=upgrade_env)
            current_revisions = _revisions(current)
            head_revisions = _revisions(heads)
            if not current_revisions or current_revisions != head_revisions:
                raise UpgradeAcceptanceError("isolated upgraded database is not at Alembic head")
            checks.append("alembic_current_head")

            _run([str(venv_python), "-m", "alembic", "check"], cwd=backend, env=upgrade_env, timeout=300)
            checks.append("alembic_metadata_clean")

            table_count_after = int(
                _run(
                    [*psql, "--command", "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"],
                    env=env,
                )
            )
            if table_count_after < table_count_before:
                raise UpgradeAcceptanceError("isolated upgrade unexpectedly reduced public table count")

        report.update(
            {
                "status": "pass",
                "source_backup_sha256": backup_hash,
                "source_revisions": source_revisions,
                "target_revisions": current_revisions,
                "public_tables_before": table_count_before,
                "public_tables_after": table_count_after,
            }
        )
        _write_report(args.output, report)
        print(f"[ok] structured existing-database upgrade evidence: {args.output}")
        return 0
    except (UpgradeAcceptanceError, OSError, UnicodeDecodeError, ValueError) as exc:
        report["error"] = str(exc)
        try:
            _write_report(args.output, report)
        except OSError:
            pass
        print(f"[failed] {exc}", file=sys.stderr)
        return 1
    finally:
        if created:
            subprocess.run(
                ["dropdb", "--if-exists", "--host", host, "--port", port, "--username", user, drill_db],
                env=env,
                check=False,
                capture_output=True,
                timeout=60,
            )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except UpgradeAcceptanceError as exc:
        print(f"[failed] {exc}", file=sys.stderr)
        raise SystemExit(1)
