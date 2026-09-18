#!/usr/bin/env python3
"""Build a release manifest only after strict CI/runtime evidence validation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from ci_acceptance import CIAcceptanceError, validate_ci_evidence
from payment_acceptance import PaymentAcceptanceError, validate_payment_evidence
from release_evidence import SHA40_RE, SHA256_RE, parse_artifact, validate_version_for_stage


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, *, label: str) -> dict:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid UTF-8 JSON") from exc
    if not isinstance(report, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return report


def _validate_database_upgrade_binding(
    deployment_path: Path,
    *,
    version: str,
    commit: str,
    environment: str,
) -> None:
    report = _load_json(deployment_path, label="deployment artifact")
    if report.get("version") != version:
        raise ValueError("deployment artifact version does not match release VERSION")
    if str(report.get("commit") or "").lower() != commit.lower():
        raise ValueError("deployment artifact commit does not match release commit")
    if report.get("environment") != environment:
        raise ValueError("deployment artifact environment does not match release environment")
    checks = report.get("checks")
    if not isinstance(checks, list) or "database_upgrade_proof_bound" not in checks:
        raise ValueError("deployment artifact is missing isolated existing-database upgrade proof")
    proof_hash = str(report.get("database_upgrade_proof_sha256") or "")
    if SHA256_RE.fullmatch(proof_hash) is None:
        raise ValueError("deployment artifact has invalid database upgrade proof SHA-256")


def _validate_wb_credential_binding(
    core_smoke_path: Path,
    deployment_path: Path,
    payment_path: Path,
    *,
    version: str,
    commit: str,
    environment: str,
) -> None:
    core = _load_json(core_smoke_path, label="core_smoke artifact")
    deployment = _load_json(deployment_path, label="deployment artifact")
    payment = _load_json(payment_path, label="payment isolation proof")
    if core.get("schema_version") != 1 or core.get("kind") != "release_smoke":
        raise ValueError("core_smoke artifact has an invalid schema")
    if core.get("status") != "pass" or core.get("version") != version:
        raise ValueError("core_smoke artifact does not match passing release VERSION")
    if str(core.get("commit") or "").lower() != commit.lower():
        raise ValueError("core_smoke artifact commit does not match release commit")
    if core.get("environment") != environment:
        raise ValueError("core_smoke artifact environment does not match release environment")
    checks = core.get("checks")
    if not isinstance(checks, dict) or checks.get("wb_credential") is not True:
        raise ValueError("core_smoke must prove live WB credential validation and cleanup")
    core_origin = str(core.get("base_origin") or "").rstrip("/")
    deployment_origin = str(deployment.get("public_origin") or "").rstrip("/")
    payment_origin = str(payment.get("base_origin") or "").rstrip("/")
    if not core_origin or core_origin != deployment_origin or core_origin != payment_origin:
        raise ValueError("core smoke, deployment and payment proof must target the same public origin")


def _bind_candidate_subproof(manifest_path: Path, *, name: str, proof_path: Path) -> None:
    manifest = _load_json(manifest_path, label="generated release manifest")
    if manifest.get("status") != "complete":
        raise ValueError("generated release manifest is not complete")
    subproofs = manifest.setdefault("candidate_subproofs", {})
    if not isinstance(subproofs, dict):
        raise ValueError("generated release manifest has invalid candidate_subproofs")
    subproofs[name] = {
        "file": proof_path.name,
        "size_bytes": proof_path.stat().st_size,
        "sha256": _sha256(proof_path),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("beta", "rc", "stable"), required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--version-file", type=Path, default=Path("VERSION"))
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument(
        "--payment-proof",
        type=Path,
        default=Path(os.environ["PAYMENT_ISOLATION_PROOF"]) if os.getenv("PAYMENT_ISOLATION_PROOF") else None,
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    environment = args.environment.strip()
    commit = args.commit.strip()
    if not environment:
        print("release_candidate_error=environment must be non-empty", file=sys.stderr)
        return 2
    if SHA40_RE.fullmatch(commit) is None:
        print("release_candidate_error=commit must be a full 40-character Git SHA", file=sys.stderr)
        return 2
    try:
        version = args.version_file.read_text(encoding="utf-8").strip()
        validate_version_for_stage(version, args.stage)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"release_candidate_error={exc}", file=sys.stderr)
        return 2

    ci_path: Path | None = None
    deployment_path: Path | None = None
    core_smoke_path: Path | None = None
    try:
        for raw in args.artifact:
            kind, path = parse_artifact(raw)
            if kind == "ci":
                if ci_path is not None:
                    raise ValueError("duplicate ci artifact")
                ci_path = path
            elif kind == "deployment":
                if deployment_path is not None:
                    raise ValueError("duplicate deployment artifact")
                deployment_path = path
            elif kind == "core_smoke":
                if core_smoke_path is not None:
                    raise ValueError("duplicate core_smoke artifact")
                core_smoke_path = path
    except ValueError as exc:
        print(f"release_candidate_error={exc}", file=sys.stderr)
        return 2
    if ci_path is None:
        print("release_candidate_error=structured ci artifact is required", file=sys.stderr)
        return 2
    if deployment_path is None:
        print("release_candidate_error=structured deployment artifact is required", file=sys.stderr)
        return 2
    if core_smoke_path is None:
        print("release_candidate_error=structured core_smoke artifact is required", file=sys.stderr)
        return 2
    if args.payment_proof is None:
        print("release_candidate_error=structured payment isolation proof is required", file=sys.stderr)
        return 2

    try:
        validate_ci_evidence(
            ci_path,
            version=version,
            commit=commit,
            environment=environment,
        )
        _validate_database_upgrade_binding(
            deployment_path,
            version=version,
            commit=commit,
            environment=environment,
        )
        validate_payment_evidence(
            args.payment_proof,
            version=version,
            commit=commit,
            environment=environment,
        )
        _validate_wb_credential_binding(
            core_smoke_path,
            deployment_path,
            args.payment_proof,
            version=version,
            commit=commit,
            environment=environment,
        )
    except (CIAcceptanceError, PaymentAcceptanceError, ValueError, OSError) as exc:
        print(f"release_candidate_error={exc}", file=sys.stderr)
        return 2

    release_evidence = Path(__file__).resolve().with_name("release_evidence.py")
    command = [
        sys.executable,
        str(release_evidence),
        "--stage",
        args.stage,
        "--environment",
        environment,
        "--commit",
        commit,
        "--version-file",
        str(args.version_file),
        "--require-structured-runtime-evidence",
        "--output",
        str(args.output),
    ]
    for artifact in args.artifact:
        command.extend(["--artifact", artifact])
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        return completed.returncode
    try:
        _bind_candidate_subproof(
            args.output,
            name="payment_isolation",
            proof_path=args.payment_proof,
        )
    except (OSError, ValueError) as exc:
        print(f"release_candidate_error={exc}", file=sys.stderr)
        return 2
    print(f"[ok] strict release candidate evidence manifest: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
