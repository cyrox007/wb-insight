#!/usr/bin/env python3
"""Самопроверка release governance для branch protection без обращения к GitHub."""

from __future__ import annotations

import sys
from pathlib import Path


OPS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(OPS_DIR))

import apply_branch_protection as protection  # noqa: E402


def _effective(policy: protection.BranchPolicy) -> dict:
    return {
        "required_status_checks": {
            "strict": True,
            "contexts": list(policy.required_contexts),
        },
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": True,
            "required_approving_review_count": 1,
        },
        "enforce_admins": {"enabled": True},
        "allow_force_pushes": {"enabled": False},
        "allow_deletions": {"enabled": False},
        "required_conversation_resolution": {"enabled": True},
    }


def main() -> int:
    policies = {item.branch: item for item in protection.POLICIES}
    assert set(policies) == {"dev", "main"}
    assert policies["dev"].required_contexts == ("branch-policy",)

    main_contexts = set(policies["main"].required_contexts)
    expected_release_contexts = {
        "branch-policy",
        "build",
        "security-tests",
        "alembic-upgrade",
        "backup-restore",
        "docker-build",
        "acceptance-tools",
        "version",
        "validate",
        "smoke-contract",
    }
    assert main_contexts == expected_release_contexts

    for policy in protection.POLICIES:
        assert protection._verify(policy, _effective(policy)) == []

    broken = _effective(policies["main"])
    broken["required_status_checks"]["contexts"].remove("build")
    broken["allow_force_pushes"] = {"enabled": True}
    problems = protection._verify(policies["main"], broken)
    assert any("build" in item for item in problems)
    assert any("force-push" in item for item in problems)

    payload = protection._payload(policies["main"])
    assert payload["required_status_checks"]["strict"] is True
    assert payload["required_pull_request_reviews"]["required_approving_review_count"] == 1
    assert payload["enforce_admins"] is True
    assert payload["allow_force_pushes"] is False
    assert payload["allow_deletions"] is False

    print("[ok] контракт branch protection соответствует release governance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
