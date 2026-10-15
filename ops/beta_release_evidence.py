#!/usr/bin/env python3
"""Канонический beta manifest с обязательными и условными поддоказательствами P40."""

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
from release_evidence import SHA40_RE, parse_artifact, validate_version_for_stage
from sber_sandbox_acceptance import (
    SberSandboxAcceptanceError,
    validate_sber_sandbox_evidence,
)
from wb_live_data_acceptance import (
    WBLiveDataAcceptanceError,
    validate_wb_live_data_evidence,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, *, label: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label}: требуется корректный UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label}: ожидается JSON-объект")
    return value


def _artifact_path(artifacts: list[str], kind: str) -> Path:
    matches: list[Path] = []
    for raw in artifacts:
        parsed_kind, path = parse_artifact(raw)
        if parsed_kind == kind:
            matches.append(path)
    if len(matches) != 1:
        raise ValueError(f"Beta evidence требует ровно один артефакт {kind}")
    return matches[0]


def _validate_beta_mail_gateway_binding(core_smoke_path: Path) -> None:
    """Проверяет реальную готовность auth-mail без привязки к поставщику."""
    report = _load_json(core_smoke_path, label="артефакт core_smoke")
    checks = report.get("checks")
    if not isinstance(checks, dict) or checks.get("mail_gateway_ready") is not True:
        raise ValueError("Beta core_smoke должен подтверждать готовность почтового шлюза")

    gateway = report.get("mail_gateway")
    if not isinstance(gateway, dict):
        raise ValueError("Beta core_smoke не содержит безопасные metadata почтового шлюза")

    provider = str(gateway.get("provider") or "").strip().lower()
    if not provider:
        raise ValueError("Beta mail evidence не содержит фактический почтовый провайдер")

    expected_provider = str(gateway.get("expected_provider") or "").strip().lower()
    if expected_provider and expected_provider != provider:
        raise ValueError(
            "Beta mail evidence не совпадает с ожидаемым провайдером: "
            f"ожидался {expected_provider}, получен {provider}"
        )

    if gateway.get("transactional") is not True:
        raise ValueError("Beta mail evidence должен подтверждать transactional capability")

    transport_kind = str(gateway.get("transport_kind") or "").strip().lower()
    if not transport_kind or transport_kind == "unknown":
        raise ValueError("Beta mail evidence не содержит тип почтового транспорта")

    if gateway.get("email_verification_ready") is not True:
        raise ValueError("Beta mail evidence должен подтверждать готовность email verification")
    if gateway.get("password_reset_ready") is not True:
        raise ValueError("Beta mail evidence должен подтверждать готовность password reset")

    source = str(gateway.get("source") or "").strip().lower()
    if source not in {"database", "environment"}:
        raise ValueError("Beta mail evidence содержит неверный источник эффективной конфигурации")


def _validate_wb_live_binding(
    proof_path: Path,
    *,
    accuracy_input_path: Path,
    data_accuracy_path: Path,
    deployment_path: Path,
    version: str,
    commit: str,
    environment: str,
) -> None:
    proof = validate_wb_live_data_evidence(
        proof_path,
        version=version,
        commit=commit,
        environment=environment,
    )
    accuracy_report = _load_json(data_accuracy_path, label="артефакт data_accuracy")
    accuracy_input = _load_json(accuracy_input_path, label="вход data-accuracy")
    accuracy_input_hash = _sha256(accuracy_input_path)
    if str(proof.get("data_accuracy_sha256") or "").lower() != _sha256(data_accuracy_path).lower():
        raise ValueError("WB live data proof не связан с переданным артефактом data_accuracy")
    if str(proof.get("accuracy_input_sha256") or "").lower() != accuracy_input_hash.lower():
        raise ValueError("WB live data proof не связан с переданным accuracy input")
    if str(accuracy_report.get("input_sha256") or "").lower() != accuracy_input_hash.lower():
        raise ValueError("Артефакт data_accuracy не связан с переданным accuracy input")
    if str(accuracy_input.get("wb_account_fingerprint") or "").lower() != str(
        proof.get("wb_account_fingerprint") or ""
    ).lower():
        raise ValueError("Accuracy input и WB live data proof относятся к разным seller account")

    deployment = _load_json(deployment_path, label="артефакт deployment")
    deployment_origin = str(deployment.get("public_origin") or "").rstrip("/")
    proof_origin = str(proof.get("public_origin") or "").rstrip("/")
    if not deployment_origin or proof_origin != deployment_origin:
        raise ValueError("WB live data proof и deployment должны использовать один public origin")


def _bind_beta_proofs(
    manifest_path: Path,
    *,
    backup_restore_path: Path,
    wb_live_data_path: Path,
    accuracy_input_path: Path,
    sber_sandbox_path: Path | None,
) -> None:
    manifest = _load_json(manifest_path, label="сгенерированный candidate manifest")
    if manifest.get("status") != "complete":
        raise ValueError("Сгенерированный candidate manifest не завершён")

    required = manifest.get("required_artifact_kinds")
    artifacts = manifest.get("artifacts")
    if not isinstance(required, list) or not isinstance(artifacts, list):
        raise ValueError("Candidate manifest содержит неверные metadata артефактов")
    if "backup_restore" not in required:
        required.append("backup_restore")
        required.sort()

    artifacts = [
        item
        for item in artifacts
        if isinstance(item, dict) and item.get("kind") != "backup_restore"
    ]
    artifacts.append(
        {
            "kind": "backup_restore",
            "file": backup_restore_path.name,
            "size_bytes": backup_restore_path.stat().st_size,
            "sha256": _sha256(backup_restore_path),
        }
    )
    manifest["artifacts"] = sorted(artifacts, key=lambda item: str(item.get("kind") or ""))
    manifest["missing_artifact_kinds"] = [
        item for item in manifest.get("missing_artifact_kinds", []) if item != "backup_restore"
    ]

    subproofs = manifest.setdefault("candidate_subproofs", {})
    if not isinstance(subproofs, dict):
        raise ValueError("Candidate manifest содержит неверный candidate_subproofs")
    for name, proof_path in (
        ("backup_restore", backup_restore_path),
        ("wb_live_data", wb_live_data_path),
        ("data_accuracy_input", accuracy_input_path),
    ):
        subproofs[name] = {
            "file": proof_path.name,
            "size_bytes": proof_path.stat().st_size,
            "sha256": _sha256(proof_path),
        }

    manifest["beta_backup_restore_required"] = True
    manifest["beta_wb_live_data_required"] = True
    manifest["beta_accuracy_input_bound"] = True

    if sber_sandbox_path is not None:
        subproofs["sber_sandbox"] = {
            "file": sber_sandbox_path.name,
            "size_bytes": sber_sandbox_path.stat().st_size,
            "sha256": _sha256(sber_sandbox_path),
        }
        manifest["beta_sber_sandbox_evidence_present"] = True

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
    parser.add_argument("--wb-live-data-proof", type=Path, required=True)
    parser.add_argument("--accuracy-input", type=Path, required=True)
    parser.add_argument(
        "--sber-sandbox-proof",
        type=Path,
        help="Необязательный merchant proof Sber sandbox; при наличии проверяется и связывается по hash",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    environment = args.environment.strip()
    commit = args.commit.strip()
    if not environment:
        print("beta_release_error=environment не должен быть пустым", file=sys.stderr)
        return 2
    if SHA40_RE.fullmatch(commit) is None:
        print("beta_release_error=commit должен быть полным 40-символьным Git SHA", file=sys.stderr)
        return 2

    try:
        version = args.version_file.read_text(encoding="utf-8").strip()
        validate_version_for_stage(version, "beta")
        data_accuracy_path = _artifact_path(args.artifact, "data_accuracy")
        deployment_path = _artifact_path(args.artifact, "deployment")
        core_smoke_path = _artifact_path(args.artifact, "core_smoke")

        _validate_beta_mail_gateway_binding(core_smoke_path)
        validate_backup_restore_evidence(
            args.backup_restore_proof,
            version=version,
            commit=commit,
            environment=environment,
        )
        _validate_wb_live_binding(
            args.wb_live_data_proof,
            accuracy_input_path=args.accuracy_input,
            data_accuracy_path=data_accuracy_path,
            deployment_path=deployment_path,
            version=version,
            commit=commit,
            environment=environment,
        )

        if args.sber_sandbox_proof is not None:
            deployment = _load_json(deployment_path, label="артефакт deployment")
            public_origin = str(deployment.get("public_origin") or "").strip()
            if not public_origin:
                raise ValueError("Артефакт deployment не содержит public_origin")
            validate_sber_sandbox_evidence(
                args.sber_sandbox_proof,
                version=version,
                commit=commit,
                environment=environment,
                public_origin=public_origin,
            )
    except (
        OSError,
        UnicodeDecodeError,
        ValueError,
        BackupRestoreAcceptanceError,
        WBLiveDataAcceptanceError,
        SberSandboxAcceptanceError,
    ) as exc:
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
        _bind_beta_proofs(
            args.output,
            backup_restore_path=args.backup_restore_proof,
            wb_live_data_path=args.wb_live_data_proof,
            accuracy_input_path=args.accuracy_input,
            sber_sandbox_path=args.sber_sandbox_proof,
        )
    except (OSError, ValueError) as exc:
        print(f"beta_release_error={exc}", file=sys.stderr)
        return 2

    suffix = " + Sber sandbox proof" if args.sber_sandbox_proof is not None else ""
    print(f"[ok] строгий beta evidence manifest с WB/data + backup/restore proof{suffix}: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
