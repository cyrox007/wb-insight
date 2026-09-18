#!/usr/bin/env python3
"""Collect sanitized production-like systemd deployment evidence for WB Insight.

The collector is intentionally read-only. It does not print environment variables,
service environments, credentials, HTTP response bodies, or provider secrets.
"""

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
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class AcceptanceError(RuntimeError):
    pass


ASSET_RE = re.compile(r"(?:src|href)=[\"'](?P<path>/assets/[^\"']+)[\"']")
REVISION_RE = re.compile(r"\b[0-9a-f]{8,40}\b", re.IGNORECASE)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
DB_UPGRADE_REQUIRED_CHECKS = {
    "backup_integrity",
    "isolated_restore",
    "alembic_upgrade",
    "alembic_current_head",
    "alembic_metadata_clean",
}


def _run(argv: list[str], *, cwd: Path | None = None, timeout: int = 30) -> str:
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd) if cwd else None,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise AcceptanceError(f"command failed to start: {argv[0]}") from exc
    if completed.returncode != 0:
        raise AcceptanceError(f"command failed: {argv[0]}")
    return completed.stdout.strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _supported_node(version: str) -> bool:
    try:
        major, minor, *_ = (int(item) for item in version.split("."))
    except (TypeError, ValueError):
        return False
    return (major == 20 and minor >= 19) or (major == 22 and minor >= 12) or major > 22


def _safe_public_origin(value: str) -> str:
    parsed = urlparse(value.strip())
    try:
        parsed_port = parsed.port
    except ValueError as exc:
        raise AcceptanceError("public base URL contains an invalid port") from exc
    if parsed.scheme != "https" or not parsed.hostname:
        raise AcceptanceError("production-like public base URL must use HTTPS")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise AcceptanceError("public base URL must not contain credentials, query or fragment")
    if parsed.path not in {"", "/"}:
        raise AcceptanceError("public base URL must be an origin without a path")
    port = f":{parsed_port}" if parsed_port else ""
    return f"https://{parsed.hostname}{port}"


def _json_get(url: str, *, timeout: int = 20) -> dict[str, Any]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "wb-insight-acceptance/1"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read()
    except Exception as exc:
        raise AcceptanceError("HTTP acceptance endpoint unavailable") from exc
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AcceptanceError("HTTP acceptance endpoint did not return JSON") from exc
    if not isinstance(payload, dict):
        raise AcceptanceError("HTTP acceptance endpoint returned an invalid JSON envelope")
    return payload


def _text_get(url: str, *, timeout: int = 20) -> str:
    request = Request(url, headers={"Accept": "text/html", "User-Agent": "wb-insight-acceptance/1"})
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310
            raw = response.read(2 * 1024 * 1024 + 1)
    except Exception as exc:
        raise AcceptanceError("public frontend is unavailable") from exc
    if len(raw) > 2 * 1024 * 1024:
        raise AcceptanceError("public frontend index is unexpectedly large")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AcceptanceError("public frontend index is not UTF-8") from exc


def _asset_set(html: str) -> set[str]:
    return {match.group("path") for match in ASSET_RE.finditer(html)}


def _alembic_revisions(output: str) -> set[str]:
    return {value.lower() for value in REVISION_RE.findall(output)}


def _validate_db_upgrade_proof(
    path: Path,
    *,
    version: str,
    commit: str,
    environment: str,
) -> None:
    if not path.is_file() or path.stat().st_size <= 0:
        raise AcceptanceError("database upgrade proof is missing or empty")
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AcceptanceError("database upgrade proof is not valid UTF-8 JSON") from exc
    if not isinstance(report, dict):
        raise AcceptanceError("database upgrade proof must contain a JSON object")
    if report.get("schema_version") != 1 or report.get("kind") != "database_upgrade":
        raise AcceptanceError("database upgrade proof has an invalid schema")
    if report.get("status") != "pass":
        raise AcceptanceError("database upgrade proof did not pass")
    if report.get("version") != version:
        raise AcceptanceError("database upgrade proof VERSION does not match deployment")
    if str(report.get("commit") or "").lower() != commit.lower():
        raise AcceptanceError("database upgrade proof commit does not match deployment")
    if report.get("environment") != environment:
        raise AcceptanceError("database upgrade proof environment does not match deployment")
    checks = report.get("checks")
    if not isinstance(checks, list) or not DB_UPGRADE_REQUIRED_CHECKS.issubset(set(checks)):
        raise AcceptanceError("database upgrade proof is missing required checks")
    source_hash = str(report.get("source_backup_sha256") or "")
    if SHA256_RE.fullmatch(source_hash) is None:
        raise AcceptanceError("database upgrade proof is missing source backup SHA-256")
    target_revisions = report.get("target_revisions")
    if not isinstance(target_revisions, list) or not target_revisions:
        raise AcceptanceError("database upgrade proof is missing target revisions")


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _self_test() -> None:
    assert _supported_node("20.19.0")
    assert _supported_node("22.12.0")
    assert _supported_node("23.0.0")
    assert not _supported_node("20.18.9")
    assert not _supported_node("18.20.8")
    assert _safe_public_origin("https://example.com/") == "https://example.com"
    assert _asset_set('<script src="/assets/app-abc.js"></script>') == {"/assets/app-abc.js"}
    assert SHA256_RE.fullmatch("a" * 64)
    print("[ok] systemd acceptance self-test")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path(os.getenv("PROJECT_DIR", "/home/projects/wb")))
    parser.add_argument("--target-branch", default=os.getenv("TARGET_BRANCH", "main"))
    parser.add_argument("--environment", default=os.getenv("ACCEPTANCE_ENVIRONMENT"))
    parser.add_argument("--public-base-url", default=os.getenv("ACCEPTANCE_BASE_URL"))
    parser.add_argument("--health-url", default=os.getenv("HEALTH_URL", "http://127.0.0.1:9001/health/ready"))
    parser.add_argument("--rollback-proof", type=Path, default=Path(os.environ["ROLLBACK_PROOF"]) if os.getenv("ROLLBACK_PROOF") else None)
    parser.add_argument("--require-rollback-proof", action="store_true", default=os.getenv("REQUIRE_ROLLBACK_PROOF", "").lower() in {"1", "true", "yes", "on"})
    parser.add_argument("--database-upgrade-proof", type=Path, default=Path(os.environ["DATABASE_UPGRADE_PROOF"]) if os.getenv("DATABASE_UPGRADE_PROOF") else None)
    parser.add_argument("--require-database-upgrade-proof", action="store_true", default=os.getenv("REQUIRE_DATABASE_UPGRADE_PROOF", "").lower() in {"1", "true", "yes", "on"})
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return 0
    if not args.environment or not args.environment.strip():
        raise AcceptanceError("--environment or ACCEPTANCE_ENVIRONMENT is required")
    if not args.public_base_url:
        raise AcceptanceError("--public-base-url or ACCEPTANCE_BASE_URL is required")
    if args.output is None:
        raise AcceptanceError("--output is required")

    environment = args.environment.strip()
    project = args.project_dir.resolve()
    backend = project / "backend"
    frontend = project / "frontend"
    version_path = project / "VERSION"
    venv = backend / "venv"
    checks: list[str] = []
    report: dict[str, Any] = {
        "schema_version": 1,
        "kind": "deployment",
        "status": "fail",
        "environment": environment,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }

    try:
        if not (project / ".git").is_dir():
            raise AcceptanceError("project directory is not a Git checkout")
        if not version_path.is_file():
            raise AcceptanceError("VERSION is missing")

        version = version_path.read_text(encoding="utf-8").strip()
        commit = _run(["git", "rev-parse", "HEAD"], cwd=project)
        branch = _run(["git", "branch", "--show-current"], cwd=project)
        if len(commit) != 40 or not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise AcceptanceError("Git HEAD is not a full commit SHA")
        if branch != args.target_branch:
            raise AcceptanceError("deployment is not on the target branch")
        if _run(["git", "status", "--porcelain"], cwd=project):
            raise AcceptanceError("working tree is not clean")
        origin_head = _run(["git", "rev-parse", f"origin/{args.target_branch}"], cwd=project)
        if origin_head != commit:
            raise AcceptanceError("local HEAD does not match origin target branch")
        checks.extend(["git_clean", "target_branch_exact_head"])

        if not venv.is_symlink():
            raise AcceptanceError("backend/venv is not the immutable release symlink")
        venv_target = venv.resolve()
        if not venv_target.name.startswith("venv.release."):
            raise AcceptanceError("backend/venv does not target a venv.release.* directory")
        python_version = _run([str(venv / "bin" / "python"), "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"])
        if not python_version.startswith("3.12."):
            raise AcceptanceError("active backend runtime is not Python 3.12")
        node_version = _run(["node", "-p", "process.versions.node"])
        if not _supported_node(node_version):
            raise AcceptanceError("active Node runtime is outside the supported release line")
        checks.extend(["immutable_release_venv", "python_3_12", "supported_node"])

        for service in ("wb-backend", "wb-celery", "wb-celery-beat"):
            if _run(["systemctl", "is-active", service]) != "active":
                raise AcceptanceError(f"systemd service is not active: {service}")
            enabled = _run(["systemctl", "is-enabled", service])
            if enabled not in {"enabled", "static"}:
                raise AcceptanceError(f"systemd service is not enabled: {service}")
        checks.append("systemd_services_active_enabled")

        ping = _run(
            [str(venv / "bin" / "python"), "-m", "celery", "-A", "celery_app:celery_app", "inspect", "ping", "--timeout=5"],
            cwd=backend,
            timeout=15,
        )
        if "pong" not in ping.lower():
            raise AcceptanceError("Celery worker did not answer inspect ping")
        checks.append("celery_worker_ping")

        current = _run([str(venv / "bin" / "python"), "-m", "alembic", "current"], cwd=backend)
        heads = _run([str(venv / "bin" / "python"), "-m", "alembic", "heads"], cwd=backend)
        current_revisions = _alembic_revisions(current)
        head_revisions = _alembic_revisions(heads)
        if not current_revisions or current_revisions != head_revisions:
            raise AcceptanceError("database Alembic revision does not match repository head")
        checks.append("alembic_at_head")

        database_upgrade_sha = None
        if args.database_upgrade_proof is not None:
            proof = args.database_upgrade_proof.resolve()
            _validate_db_upgrade_proof(
                proof,
                version=version,
                commit=commit,
                environment=environment,
            )
            database_upgrade_sha = _sha256(proof)
            checks.append("database_upgrade_proof_bound")
        elif args.require_database_upgrade_proof:
            raise AcceptanceError("isolated existing-database upgrade proof is required")

        _run(["nginx", "-t"])
        checks.append("nginx_config_valid")

        local_ready = _json_get(args.health_url)
        if local_ready.get("status") != "ok" or local_ready.get("version") != version:
            raise AcceptanceError("local readiness/version check failed")
        checks.append("local_readiness")

        public_origin = _safe_public_origin(args.public_base_url)
        public_ready = _json_get(f"{public_origin}/api/health/ready")
        if public_ready.get("status") != "ok" or public_ready.get("version") != version:
            raise AcceptanceError("public HTTPS readiness/version check failed")
        checks.append("public_https_readiness")

        built_index = (frontend / "dist" / "index.html").read_text(encoding="utf-8")
        public_index = _text_get(f"{public_origin}/")
        built_assets = _asset_set(built_index)
        public_assets = _asset_set(public_index)
        if not built_assets or built_assets != public_assets:
            raise AcceptanceError("public frontend assets do not match current frontend/dist build")
        checks.append("frontend_bundle_published")

        rollback_sha = None
        if args.rollback_proof is not None:
            proof = args.rollback_proof.resolve()
            if not proof.is_file() or proof.stat().st_size <= 0:
                raise AcceptanceError("rollback proof is missing or empty")
            rollback_sha = _sha256(proof)
            checks.append("rollback_proof_bound")
        elif args.require_rollback_proof:
            raise AcceptanceError("rollback proof is required for beta deployment evidence")

        report.update(
            {
                "status": "pass",
                "version": version,
                "commit": commit,
                "branch": branch,
                "public_origin": public_origin,
                "runtime": {
                    "python": python_version,
                    "node": node_version,
                    "venv_release": venv_target.name,
                    "alembic_revisions": sorted(current_revisions),
                },
                "database_upgrade_proof_sha256": database_upgrade_sha,
                "rollback_proof_sha256": rollback_sha,
            }
        )
        _write_report(args.output, report)
        print(f"[ok] structured deployment evidence: {args.output}")
        return 0
    except (AcceptanceError, OSError, UnicodeDecodeError) as exc:
        report["error"] = str(exc)
        try:
            _write_report(args.output, report)
        except OSError:
            pass
        print(f"[failed] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
