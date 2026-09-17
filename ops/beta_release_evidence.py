#!/usr/bin/env python3
"""Canonical beta manifest entrypoint with mandatory backup/restore proof."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from backup_restore_acceptance import (
    BackupRestoreAcceptanceError,
    validate_backup_restore_evidence,
)
from release_evidence import SHA40_RE, validate_version_for_stage


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bind_backup_restore(manifest_path: Path, proof_path: Path) -> None:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("generated candidate manifest is invalid") from exc
    if not isinstance(manifest, dict) or manifest.get("status") != "complete":
        raise ValueError("generated candidate manifest is not complete")

    required = manifest.get("required_artifact_kinds")
    artifacts = manifest.get("artifacts")
    if not isinstance(required, list) or not isinstance(artifacts, list):
        raise ValueError("generated candidate manifest has invalid artifact metadata")
    if "backup_restore" not in required:
        required.append("backup_restore")
        required.sort()
    artifacts = [item for item in artifacts if isinstance(item, dict) and item.get("kind") != "backup_restore"]
    artifacts.append(
        {
            "kind": "backup_restore",
            "file": proof_path.name,
            "size_bytes": proof_path.stat().st_size,
            "sha256": _sha256(proof_path),
        }
    )
    manifest["artifacts"] = sorted(artifacts, key=lambda item: str(item.get("kind") or ""))
    manifest["missing_artifact_kinds"] = [
        item for item in manifest.get("missing_artifact_kinds", []) if item != "backup_restore"
    ]
    subproofs = manifest.setdefault("candidate_subproofs", {})
    if not isinstance(subproofs, dict):
        raise ValueError("generated candidate manifest has invalid candidate_subproofs")
    subproofs["backup_restore"] = {
        "file": proof_path.name,
        "size_bytes": proof_path.stat().st_size,
        "sha256": _sha256(proof_path),
    }
    manifest["beta_backup_restore_required"] = True
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--version-file", type=Path, default=Path("VERSION"))
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("--payment-proof", type=Path, required=True)
    parser.add_argument("--backup-restore-proof", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    environment = args.environment.strip()
    commit = args.commit.strip()
    if not environment:
        print("beta_release_error=environment must be non-empty", file=sys.stderr)
        return 2
    if SHA40_RE.fullmatch(commit) is None:
        print("beta_release_error=commit must be a full 40-character Git SHA", file=sys.stderr)
        return 2
    try:
        version = args.version_file.read_text(encoding="utf-8").strip()
        validate_version_for_stage(version, "beta")
        validate_backup_restore_evidence(
            args.backup_restore_proof,
            version=version,
            commit=commit,
            environment=environment,
        )
    except (OSError, UnicodeDecodeError, ValueError, BackupRestoreAcceptanceError) as exc:
        print(f"beta_release_error={exc}", file=sys.stderr)
        return 2

    candidate = Path(__file__).resolve().with_name("release_candidate_evidence.py")
    command = [
        sys.executable,
        str(candidate),
        "--stage",
        "beta",
        "--environment",
        environment,
        "--commit",
        commit,
        "--version-file",
        str(args.version_file),
        "--payment-proof",
        str(args.payment_proof),
        "--output",
        str(args.output),
    ]
    for artifact in args.artifact:
        if artifact.split("=", 1)[0].strip() == "backup_restore":
            continue
        command.extend(["--artifact", artifact])
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        return completed.returncode
    try:
        _bind_backup_restore(args.output, args.backup_restore_proof)
    except (OSError, ValueError) as exc:
        print(f"beta_release_error={exc}", file=sys.stderr)
        return 2
    print(f"[ok] strict beta evidence manifest with backup/restore proof: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
