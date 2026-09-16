#!/usr/bin/env python3
"""Validate and bind human-reviewed WB Insight desktop/mobile UX evidence.

This tool deliberately does not claim to judge screenshots. A human reviewer marks
required states as pass and supplies evidence files; the runner checks completeness,
exact release/environment binding and immutable SHA-256 references for those files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
ALLOWED_EVIDENCE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".pdf", ".mp4"}
MAX_EVIDENCE_BYTES = 100 * 1024 * 1024
VIEWPORTS = {"desktop", "mobile"}

DEFAULT_SCENARIOS = {
    "public.home",
    "auth.verify_email",
    "auth.reset_password",
    "billing.success",
    "dashboard.overview",
    "dashboard.profile",
    "dashboard.account_security",
    "dashboard.unit_economy",
    "dashboard.finance",
    "dashboard.stocks",
    "dashboard.prices",
    "dashboard.ads",
    "control_panel.overview",
    "control_panel.users",
    "control_panel.roles",
    "control_panel.tariffs",
    "control_panel.payments",
    "control_panel.mail",
    "control_panel.audit",
}

EXTRA_REQUIRED = {
    ("public.home", "desktop", "registration_form"),
    ("public.home", "mobile", "registration_form"),
    ("public.home", "desktop", "validation_error"),
    ("public.home", "mobile", "validation_error"),
    ("auth.verify_email", "desktop", "invalid_or_expired"),
    ("auth.reset_password", "desktop", "invalid_or_expired"),
    ("dashboard.overview", "desktop", "loading"),
    ("dashboard.overview", "desktop", "empty"),
    ("dashboard.overview", "desktop", "error"),
    ("control_panel.users", "desktop", "loading"),
    ("control_panel.users", "desktop", "empty"),
    ("control_panel.users", "desktop", "error"),
    ("control_panel.payments", "desktop", "loading"),
    ("control_panel.payments", "desktop", "empty"),
    ("control_panel.payments", "desktop", "error"),
    ("control_panel.mail", "desktop", "loading"),
    ("control_panel.mail", "desktop", "empty"),
    ("control_panel.mail", "desktop", "error"),
}

REQUIRED_CHECKS = {
    (scenario, viewport, "default")
    for scenario in DEFAULT_SCENARIOS
    for viewport in sorted(VIEWPORTS)
} | EXTRA_REQUIRED


class UXAcceptanceError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_identity(project: Path) -> tuple[str, str]:
    import subprocess

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project,
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UXAcceptanceError("could not read Git HEAD") from exc
    commit = completed.stdout.strip() if completed.returncode == 0 else ""
    if not SHA40_RE.fullmatch(commit):
        raise UXAcceptanceError("Git HEAD is not a full commit SHA")

    version_path = project / "VERSION"
    if not version_path.is_file():
        raise UXAcceptanceError("VERSION is missing")
    version = version_path.read_text(encoding="utf-8").strip()
    if not version:
        raise UXAcceptanceError("VERSION is empty")
    return commit, version


def _load_input(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise UXAcceptanceError("input must be valid UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise UXAcceptanceError("input must contain a JSON object")
    return value


def _parse_reviewed_at(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise UXAcceptanceError("reviewed_at is required")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise UXAcceptanceError("reviewed_at must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise UXAcceptanceError("reviewed_at must contain a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def _require_safe_note(value: object) -> str | None:
    if value is None:
        return None
    note = str(value).strip()
    if not note:
        return None
    if len(note) > 500:
        raise UXAcceptanceError("UX evidence note is too long")
    return note


def _evidence_item(raw: dict[str, Any], *, base_dir: Path) -> tuple[tuple[str, str, str], dict[str, Any]]:
    scenario = str(raw.get("scenario") or "").strip()
    viewport = str(raw.get("viewport") or "").strip()
    state = str(raw.get("state") or "").strip()
    status = str(raw.get("status") or "").strip().lower()
    key = (scenario, viewport, state)

    if key not in REQUIRED_CHECKS:
        raise UXAcceptanceError(
            f"unknown UX requirement: {scenario}/{viewport}/{state}"
        )
    if status != "pass":
        raise UXAcceptanceError(
            f"UX requirement did not pass: {scenario}/{viewport}/{state}"
        )

    raw_path = str(raw.get("evidence_file") or "").strip()
    if not raw_path:
        raise UXAcceptanceError(
            f"evidence_file is required for {scenario}/{viewport}/{state}"
        )
    path = Path(raw_path)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    else:
        path = path.resolve()
    if not path.is_file():
        raise UXAcceptanceError(
            f"UX evidence file is missing for {scenario}/{viewport}/{state}"
        )
    if path.suffix.lower() not in ALLOWED_EVIDENCE_SUFFIXES:
        raise UXAcceptanceError("UX evidence must be PNG/JPEG/WEBP/PDF/MP4")
    size = path.stat().st_size
    if size <= 0 or size > MAX_EVIDENCE_BYTES:
        raise UXAcceptanceError("UX evidence file size is outside the accepted range")

    return key, {
        "scenario": scenario,
        "viewport": viewport,
        "state": state,
        "status": "pass",
        "evidence_file": path.name,
        "evidence_size_bytes": size,
        "evidence_sha256": _sha256(path),
        "note": _require_safe_note(raw.get("note")),
    }


def _template(environment: str, version: str, commit: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "environment": environment,
        "version": version,
        "commit": commit,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "reviewer_reference": "replace-with-internal-review-reference",
        "checks": [
            {
                "scenario": scenario,
                "viewport": viewport,
                "state": state,
                "status": "pending",
                "evidence_file": "",
                "note": "",
            }
            for scenario, viewport, state in sorted(REQUIRED_CHECKS)
        ],
    }


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _self_test() -> None:
    assert ("dashboard.overview", "desktop", "error") in REQUIRED_CHECKS
    assert ("control_panel.audit", "mobile", "default") in REQUIRED_CHECKS
    assert ("control_panel.mail", "desktop", "empty") in REQUIRED_CHECKS
    assert len(REQUIRED_CHECKS) >= 50
    example = _template("staging-ci", "0.9.0-beta.1", "0" * 40)
    assert len(example["checks"]) == len(REQUIRED_CHECKS)
    assert all(item["status"] == "pending" for item in example["checks"])
    print("[ok] UX acceptance self-test")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-dir", type=Path, default=Path(os.getenv("PROJECT_DIR", "/home/projects/wb")))
    parser.add_argument("--environment", default=os.getenv("ACCEPTANCE_ENVIRONMENT"))
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--write-template", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return 0
    environment = str(args.environment or "").strip()
    if not environment:
        raise UXAcceptanceError("--environment or ACCEPTANCE_ENVIRONMENT is required")

    project = args.project_dir.resolve()
    if not (project / ".git").is_dir():
        raise UXAcceptanceError("project directory is not a Git checkout")
    commit, version = _git_identity(project)

    if args.write_template:
        _write(args.write_template, _template(environment, version, commit))
        print(f"[ok] UX acceptance template: {args.write_template}")
        return 0

    if args.input is None or args.output is None:
        raise UXAcceptanceError("--input and --output are required")

    payload = _load_input(args.input)
    if payload.get("schema_version") != 1:
        raise UXAcceptanceError("UX input must use schema_version=1")
    if payload.get("environment") != environment:
        raise UXAcceptanceError("UX input environment does not match requested environment")
    if payload.get("version") != version:
        raise UXAcceptanceError("UX input version does not match current VERSION")
    if str(payload.get("commit") or "").lower() != commit.lower():
        raise UXAcceptanceError("UX input commit does not match current Git HEAD")
    reviewed_at = _parse_reviewed_at(payload.get("reviewed_at"))
    reviewer_reference = str(payload.get("reviewer_reference") or "").strip()
    if not reviewer_reference or reviewer_reference.startswith("replace-with-"):
        raise UXAcceptanceError("reviewer_reference must identify the completed review")
    if len(reviewer_reference) > 160:
        raise UXAcceptanceError("reviewer_reference is too long")

    raw_checks = payload.get("checks")
    if not isinstance(raw_checks, list):
        raise UXAcceptanceError("UX input checks must be a list")

    seen: set[tuple[str, str, str]] = set()
    evidence: list[dict[str, Any]] = []
    for raw in raw_checks:
        if not isinstance(raw, dict):
            raise UXAcceptanceError("every UX check must be an object")
        key, item = _evidence_item(raw, base_dir=args.input.resolve().parent)
        if key in seen:
            raise UXAcceptanceError(
                f"duplicate UX requirement: {'/'.join(key)}"
            )
        seen.add(key)
        evidence.append(item)

    missing = sorted(REQUIRED_CHECKS - seen)
    if missing:
        preview = ", ".join("/".join(item) for item in missing[:5])
        suffix = "..." if len(missing) > 5 else ""
        raise UXAcceptanceError(
            f"UX evidence is incomplete ({len(missing)} missing): {preview}{suffix}"
        )

    report = {
        "schema_version": 1,
        "kind": "ux_smoke",
        "status": "pass",
        "environment": environment,
        "version": version,
        "commit": commit,
        "reviewed_at": reviewed_at,
        "reviewer_reference": reviewer_reference,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "required_check_count": len(REQUIRED_CHECKS),
        "passed_check_count": len(seen),
        "evidence": sorted(
            evidence,
            key=lambda item: (item["scenario"], item["viewport"], item["state"]),
        ),
    }
    _write(args.output, report)
    print(f"[ok] structured UX smoke evidence: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except UXAcceptanceError as exc:
        print(f"[failed] {exc}", file=sys.stderr)
        raise SystemExit(1)
