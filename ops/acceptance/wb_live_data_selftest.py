#!/usr/bin/env python3
"""Secret-free regression contract for P40 live WB/data provenance binding."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from beta_release_evidence import _sha256, _validate_wb_live_binding
from wb_live_data_acceptance import WBLiveDataAcceptanceError


COMMIT = "0123456789abcdef0123456789abcdef01234567"
VERSION = "0.9.0-beta.1"
ENVIRONMENT = "acceptance-test"
ORIGIN = "https://example.com"
FINGERPRINT = "a" * 64


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as raw_dir:
        root = Path(raw_dir)
        accuracy_input = root / "accuracy-input.json"
        data_accuracy = root / "data-accuracy.json"
        deployment = root / "deployment.json"
        wb_proof = root / "wb-live-data.json"

        _write(
            accuracy_input,
            {
                "dataset_id": "fixture",
                "seller_alias": "seller-fixture",
                "wb_account_fingerprint": FINGERPRINT,
                "periods": [{"label": str(index), "metrics": []} for index in range(3)],
            },
        )
        _write(
            data_accuracy,
            {
                "schema_version": 1,
                "status": "pass",
                "period_count": 3,
                "metric_count": 1,
                "input_sha256": _sha256(accuracy_input),
                "policy_sha256": "b" * 64,
            },
        )
        _write(deployment, {"public_origin": ORIGIN})
        _write(
            wb_proof,
            {
                "schema_version": 1,
                "kind": "wb_live_data",
                "status": "pass",
                "version": VERSION,
                "commit": COMMIT,
                "environment": ENVIRONMENT,
                "public_origin": ORIGIN,
                "wb_account_fingerprint": FINGERPRINT,
                "accuracy_input_sha256": _sha256(accuracy_input),
                "data_accuracy_sha256": _sha256(data_accuracy),
                "period_count": 3,
                "metric_count": 1,
                "checks": {
                    "authenticated_account": True,
                    "live_wb_credential_validated": True,
                    "temporary_credential_removed": True,
                    "account_fingerprint_matched": True,
                    "data_accuracy_passed": True,
                    "minimum_period_coverage": True,
                },
            },
        )

        _validate_wb_live_binding(
            wb_proof,
            accuracy_input_path=accuracy_input,
            data_accuracy_path=data_accuracy,
            deployment_path=deployment,
            version=VERSION,
            commit=COMMIT,
            environment=ENVIRONMENT,
        )

        tampered_input = json.loads(accuracy_input.read_text(encoding="utf-8"))
        tampered_input["wb_account_fingerprint"] = "c" * 64
        _write(accuracy_input, tampered_input)
        try:
            _validate_wb_live_binding(
                wb_proof,
                accuracy_input_path=accuracy_input,
                data_accuracy_path=data_accuracy,
                deployment_path=deployment,
                version=VERSION,
                commit=COMMIT,
                environment=ENVIRONMENT,
            )
        except (ValueError, WBLiveDataAcceptanceError):
            pass
        else:
            raise AssertionError("tampered accuracy input unexpectedly passed live WB binding")

    print("[ok] WB live data binding self-test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
