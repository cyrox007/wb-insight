#!/usr/bin/env python3
"""Self-test for strict P40 runtime evidence validation."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from release_evidence import (
    ACCOUNT_LIFECYCLE_REQUIRED_CHECKS,
    CORE_SMOKE_REQUIRED_CHECKS,
    DEPLOYMENT_REQUIRED_CHECKS,
    validate_deployment_evidence,
    validate_release_smoke_evidence,
)


VERSION = "0.9.0-beta.1"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
ENVIRONMENT = "staging-ci-fixture"


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def main() -> int:
    with TemporaryDirectory() as raw_tmp:
        tmp = Path(raw_tmp)
        deployment = tmp / "deployment.json"
        smoke = tmp / "release-smoke.json"

        _write(
            deployment,
            {
                "schema_version": 1,
                "kind": "deployment",
                "status": "pass",
                "environment": ENVIRONMENT,
                "version": VERSION,
                "commit": COMMIT,
                "public_origin": "https://staging.example.com",
                "checks": {name: True for name in DEPLOYMENT_REQUIRED_CHECKS},
                "runtime": {
                    "python": "3.12.13",
                    "node": "22.23.2",
                    "venv_release": "venv.release.20260916T180000Z",
                    "alembic_revisions": ["abcdef123456"],
                },
                "rollback_proof_sha256": "a" * 64,
            },
        )
        _write(
            smoke,
            {
                "schema_version": 1,
                "kind": "release_smoke",
                "status": "pass",
                "version": VERSION,
                "base_origin": "https://staging.example.com",
                "checks": {
                    name: True
                    for name in CORE_SMOKE_REQUIRED_CHECKS | ACCOUNT_LIFECYCLE_REQUIRED_CHECKS
                },
            },
        )

        validate_deployment_evidence(
            deployment,
            version=VERSION,
            commit=COMMIT,
            environment=ENVIRONMENT,
        )
        validate_release_smoke_evidence(smoke, version=VERSION, artifact_kind="core_smoke")
        validate_release_smoke_evidence(smoke, version=VERSION, artifact_kind="account_lifecycle")

        broken = json.loads(deployment.read_text(encoding="utf-8"))
        broken["commit"] = "f" * 40
        _write(deployment, broken)
        try:
            validate_deployment_evidence(
                deployment,
                version=VERSION,
                commit=COMMIT,
                environment=ENVIRONMENT,
            )
        except ValueError as exc:
            assert "commit" in str(exc)
        else:
            raise AssertionError("mismatched deployment commit unexpectedly passed")

        broken_smoke = json.loads(smoke.read_text(encoding="utf-8"))
        broken_smoke["checks"]["password_reset"] = False
        _write(smoke, broken_smoke)
        try:
            validate_release_smoke_evidence(
                smoke,
                version=VERSION,
                artifact_kind="account_lifecycle",
            )
        except ValueError as exc:
            assert "password_reset" in str(exc)
        else:
            raise AssertionError("missing lifecycle check unexpectedly passed")

    print("[ok] structured runtime evidence self-test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
