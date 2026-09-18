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
    SECRETS_REVIEW_CORE_NAMES,
    UX_REQUIRED_CHECKS,
    validate_deployment_evidence,
    validate_release_smoke_evidence,
    validate_secrets_review_evidence,
    validate_ux_smoke_evidence,
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
        secrets_review = tmp / "secrets-review.json"
        ux_smoke = tmp / "ux-smoke.json"

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
                "checks": sorted(DEPLOYMENT_REQUIRED_CHECKS),
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
                "commit": COMMIT,
                "environment": ENVIRONMENT,
                "base_origin": "https://staging.example.com",
                "checks": {
                    name: True
                    for name in CORE_SMOKE_REQUIRED_CHECKS | ACCOUNT_LIFECYCLE_REQUIRED_CHECKS
                },
            },
        )
        _write(
            secrets_review,
            {
                "schema_version": 1,
                "kind": "secrets_review",
                "status": "pass",
                "version": VERSION,
                "commit": COMMIT,
                "environment": ENVIRONMENT,
                "secret_names_checked": sorted(SECRETS_REVIEW_CORE_NAMES),
                "findings_count": 0,
                "findings": [],
                "git_history_checked": True,
                "journal_checked": True,
                "scan_stats": {
                    "git_worktree_files": 100,
                    "git_worktree_bytes": 1000,
                    "git_history_blobs": 200,
                    "git_history_bytes": 2000,
                    "frontend_files": 5,
                    "frontend_bytes": 500,
                    "extra_log_files": 0,
                    "extra_log_bytes": 0,
                    "journal_bytes": 0,
                },
            },
        )
        _write(
            ux_smoke,
            {
                "schema_version": 1,
                "kind": "ux_smoke",
                "status": "pass",
                "version": VERSION,
                "commit": COMMIT,
                "environment": ENVIRONMENT,
                "reviewed_at": "2026-09-16T18:30:00+00:00",
                "reviewer_reference": "ci-human-review-fixture",
                "required_check_count": len(UX_REQUIRED_CHECKS),
                "passed_check_count": len(UX_REQUIRED_CHECKS),
                "evidence": [
                    {
                        "scenario": scenario,
                        "viewport": viewport,
                        "state": state,
                        "status": "pass",
                        "evidence_file": f"{index:03d}.png",
                        "evidence_size_bytes": 1024 + index,
                        "evidence_sha256": "b" * 64,
                        "note": None,
                    }
                    for index, (scenario, viewport, state) in enumerate(
                        sorted(UX_REQUIRED_CHECKS), start=1
                    )
                ],
            },
        )

        validate_deployment_evidence(
            deployment,
            version=VERSION,
            commit=COMMIT,
            environment=ENVIRONMENT,
        )
        validate_release_smoke_evidence(
            smoke,
            version=VERSION,
            commit=COMMIT,
            environment=ENVIRONMENT,
            artifact_kind="core_smoke",
        )
        validate_release_smoke_evidence(
            smoke,
            version=VERSION,
            commit=COMMIT,
            environment=ENVIRONMENT,
            artifact_kind="account_lifecycle",
        )
        validate_secrets_review_evidence(
            secrets_review,
            version=VERSION,
            commit=COMMIT,
            environment=ENVIRONMENT,
        )
        validate_ux_smoke_evidence(
            ux_smoke,
            version=VERSION,
            commit=COMMIT,
            environment=ENVIRONMENT,
        )

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
                commit=COMMIT,
                environment=ENVIRONMENT,
                artifact_kind="account_lifecycle",
            )
        except ValueError as exc:
            assert "password_reset" in str(exc)
        else:
            raise AssertionError("missing lifecycle check unexpectedly passed")

        # Restore the passing smoke and prove exact release provenance is enforced.
        passing_smoke = {
            "schema_version": 1,
            "kind": "release_smoke",
            "status": "pass",
            "version": VERSION,
            "commit": "f" * 40,
            "environment": ENVIRONMENT,
            "base_origin": "https://staging.example.com",
            "checks": {
                name: True
                for name in CORE_SMOKE_REQUIRED_CHECKS | ACCOUNT_LIFECYCLE_REQUIRED_CHECKS
            },
        }
        _write(smoke, passing_smoke)
        try:
            validate_release_smoke_evidence(
                smoke,
                version=VERSION,
                commit=COMMIT,
                environment=ENVIRONMENT,
                artifact_kind="core_smoke",
            )
        except ValueError as exc:
            assert "commit" in str(exc)
        else:
            raise AssertionError("mismatched smoke commit unexpectedly passed")

        broken_secrets = json.loads(secrets_review.read_text(encoding="utf-8"))
        broken_secrets["status"] = "fail"
        broken_secrets["findings_count"] = 1
        broken_secrets["findings"] = [
            {"secret_name": "JWT_SECRET_KEY", "scopes": ["frontend_dist"]}
        ]
        _write(secrets_review, broken_secrets)
        try:
            validate_secrets_review_evidence(
                secrets_review,
                version=VERSION,
                commit=COMMIT,
                environment=ENVIRONMENT,
            )
        except ValueError as exc:
            assert "status=pass" in str(exc) or "findings" in str(exc)
        else:
            raise AssertionError("secret leak finding unexpectedly passed")

        broken_ux = json.loads(ux_smoke.read_text(encoding="utf-8"))
        broken_ux["evidence"] = broken_ux["evidence"][:-1]
        broken_ux["passed_check_count"] -= 1
        _write(ux_smoke, broken_ux)
        try:
            validate_ux_smoke_evidence(
                ux_smoke,
                version=VERSION,
                commit=COMMIT,
                environment=ENVIRONMENT,
            )
        except ValueError as exc:
            assert "pass every required UX check" in str(exc) or "incomplete" in str(exc)
        else:
            raise AssertionError("incomplete UX evidence unexpectedly passed")

    print("[ok] structured runtime evidence self-test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
