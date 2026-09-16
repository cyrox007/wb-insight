#!/usr/bin/env python3
"""Self-test strict release-candidate deployment/database-upgrade binding."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from release_candidate_evidence import _validate_database_upgrade_binding


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
