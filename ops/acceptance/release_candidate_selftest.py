#!/usr/bin/env python3
"""Self-test strict release-candidate deployment/database-upgrade binding."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from release_candidate_evidence import (
    _validate_database_upgrade_binding,
    _validate_wb_credential_binding,
)


VERSION = "0.9.0-beta.1"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
ENVIRONMENT = "staging-ci-fixture"


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def main() -> int:
    with TemporaryDirectory() as raw_tmp:
        path = Path(raw_tmp) / "deployment.json"
        good = {
            "schema_version": 1,
            "kind": "deployment",
            "status": "pass",
            "version": VERSION,
            "commit": COMMIT,
            "environment": ENVIRONMENT,
            "checks": ["database_upgrade_proof_bound"],
            "database_upgrade_proof_sha256": "a" * 64,
        }
        _write(path, good)
        _validate_database_upgrade_binding(
            path,
            version=VERSION,
            commit=COMMIT,
            environment=ENVIRONMENT,
        )

        broken = dict(good)
        broken["checks"] = []
        _write(path, broken)
        try:
            _validate_database_upgrade_binding(
                path,
                version=VERSION,
                commit=COMMIT,
                environment=ENVIRONMENT,
            )
        except ValueError as exc:
            assert "database" in str(exc).lower()
        else:
            raise AssertionError("missing database upgrade proof unexpectedly passed")

        core_smoke = Path(raw_tmp) / "core-smoke.json"
        payment = Path(raw_tmp) / "payment.json"
        _write(
            core_smoke,
            {
                "schema_version": 1,
                "kind": "release_smoke",
                "status": "pass",
                "version": VERSION,
                "commit": COMMIT,
                "environment": ENVIRONMENT,
                "base_origin": "https://staging.example.com",
                "checks": {"wb_credential": True},
            },
        )
        deployment_payload = dict(good)
        deployment_payload["public_origin"] = "https://staging.example.com"
        _write(path, deployment_payload)
        _write(
            payment,
            {
                "base_origin": "https://staging.example.com",
            },
        )
        _validate_wb_credential_binding(
            core_smoke,
            path,
            payment,
            version=VERSION,
            commit=COMMIT,
            environment=ENVIRONMENT,
        )

        mismatched_core = json.loads(core_smoke.read_text(encoding="utf-8"))
        mismatched_core["environment"] = "other-environment"
        _write(core_smoke, mismatched_core)
        try:
            _validate_wb_credential_binding(
                core_smoke,
                path,
                payment,
                version=VERSION,
                commit=COMMIT,
                environment=ENVIRONMENT,
            )
        except ValueError as exc:
            assert "environment" in str(exc)
        else:
            raise AssertionError("mismatched core smoke environment unexpectedly passed")

        broken = dict(good)
        broken["database_upgrade_proof_sha256"] = "invalid"
        _write(path, broken)
        try:
            _validate_database_upgrade_binding(
                path,
                version=VERSION,
                commit=COMMIT,
                environment=ENVIRONMENT,
            )
        except ValueError as exc:
            assert "sha-256" in str(exc).lower()
        else:
            raise AssertionError("invalid database upgrade hash unexpectedly passed")

    print("[ok] release candidate database upgrade binding self-test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
