#!/usr/bin/env python3
"""Самопроверка обязательных и условных beta-поддоказательств."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from beta_release_evidence import _bind_beta_proofs, _validate_beta_mail_gateway_binding


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _manifest() -> dict:
    return {
        "schema_version": 2,
        "stage": "beta",
        "status": "complete",
        "required_artifact_kinds": ["ci", "deployment"],
        "missing_artifact_kinds": [],
        "artifacts": [],
        "candidate_subproofs": {"payment_isolation": {"sha256": "a" * 64}},
    }


def _mail_gateway(provider: str, *, expected_provider: str | None = None) -> dict:
    return {
        "schema_version": 1,
        "kind": "release_smoke",
        "status": "pass",
        "checks": {"mail_gateway_ready": True},
        "mail_gateway": {
            "provider": provider,
            "expected_provider": expected_provider,
            "source": "database",
            "config_source": "auto",
            "transport_kind": "https_api",
            "transactional": True,
            "marketing": True,
            "one_click_unsubscribe": True,
            "email_verification_ready": True,
            "password_reset_ready": True,
        },
    }


def main() -> int:
    with TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        manifest = tmp / "release-manifest.json"
        backup = tmp / "backup-restore.json"
        wb_live = tmp / "wb-live-data.json"
        accuracy_input = tmp / "accuracy-input.json"
        sber = tmp / "sber-sandbox.json"

        _write(backup, {"kind": "backup_restore", "status": "pass"})
        _write(wb_live, {"kind": "wb_live_data", "status": "pass"})
        _write(accuracy_input, {"dataset_id": "fixture", "wb_account_fingerprint": "b" * 64})
        _write(sber, {"kind": "sber_sandbox", "status": "pass"})

        core_smoke = tmp / "core-smoke.json"

        _write(core_smoke, _mail_gateway("resend", expected_provider="resend"))
        _validate_beta_mail_gateway_binding(core_smoke)

        _write(core_smoke, _mail_gateway("smtp"))
        _validate_beta_mail_gateway_binding(core_smoke)

        broken_mail = _mail_gateway("resend", expected_provider="rusender")
        _write(core_smoke, broken_mail)
        try:
            _validate_beta_mail_gateway_binding(core_smoke)
        except ValueError as exc:
            assert "ожидаемым провайдером" in str(exc)
        else:
            raise AssertionError("Несовпадающий ожидаемый провайдер неожиданно прошёл beta binding")

        broken_capability = _mail_gateway("resend")
        broken_capability["mail_gateway"]["transactional"] = False
        _write(core_smoke, broken_capability)
        try:
            _validate_beta_mail_gateway_binding(core_smoke)
        except ValueError as exc:
            assert "transactional capability" in str(exc)
        else:
            raise AssertionError("Провайдер без transactional capability неожиданно прошёл beta binding")

        _write(manifest, _manifest())
        _bind_beta_proofs(
            manifest,
            backup_restore_path=backup,
            wb_live_data_path=wb_live,
            accuracy_input_path=accuracy_input,
            sber_sandbox_path=sber,
        )
        report = json.loads(manifest.read_text(encoding="utf-8"))
        assert "backup_restore" in report["required_artifact_kinds"]
        assert report["beta_backup_restore_required"] is True
        assert report["beta_wb_live_data_required"] is True
        assert report["beta_accuracy_input_bound"] is True
        assert report["beta_sber_sandbox_evidence_present"] is True
        assert report["candidate_subproofs"]["backup_restore"]["sha256"] == _sha256(backup)
        assert report["candidate_subproofs"]["wb_live_data"]["sha256"] == _sha256(wb_live)
        assert report["candidate_subproofs"]["data_accuracy_input"]["sha256"] == _sha256(
            accuracy_input
        )
        assert report["candidate_subproofs"]["sber_sandbox"]["sha256"] == _sha256(sber)

        _write(manifest, _manifest())
        _bind_beta_proofs(
            manifest,
            backup_restore_path=backup,
            wb_live_data_path=wb_live,
            accuracy_input_path=accuracy_input,
            sber_sandbox_path=None,
        )
        report = json.loads(manifest.read_text(encoding="utf-8"))
        assert report["beta_wb_live_data_required"] is True
        assert report["beta_accuracy_input_bound"] is True
        assert "sber_sandbox" not in report["candidate_subproofs"]
        assert "beta_sber_sandbox_evidence_present" not in report

    print("[ok] provider-neutral beta subproof self-test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
