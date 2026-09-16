#!/usr/bin/env python3
"""Build and validate a WB Insight release-evidence manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BETA_REQUIRED = {
    "ci",
    "deployment",
    "core_smoke",
    "account_lifecycle",
    "ux_smoke",
    "secrets_review",
    "data_accuracy",
}

REQUIRED = {
    "beta": BETA_REQUIRED,
    "rc": BETA_REQUIRED
    | {
        "wb_full_sync",
        "sber_payment",
        "operations",
        "backup_restore",
        "legal",
    },
    "stable": BETA_REQUIRED
    | {
        "wb_full_sync",
        "sber_payment",
        "operations",
        "backup_restore",
        "legal",
        "rc_signoff",
    },
}

KNOWN_ARTIFACT_KINDS = set().union(*REQUIRED.values())
SHA40_RE = re.compile(r"^[0-9a-fA-F]{40}$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
VERSION_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<stage>alpha|beta|rc)\.(?P<iteration>[1-9]\d*))?$"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_artifact(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError("artifact must use kind=path format")
    kind, raw_path = value.split("=", 1)
    kind = kind.strip()
    path = Path(raw_path.strip())
    if not kind or not raw_path.strip():
        raise ValueError("artifact kind and path must be non-empty")
    if kind not in KNOWN_ARTIFACT_KINDS:
        raise ValueError(f"unknown artifact kind: {kind}")
    return kind, path


def validate_version_for_stage(version: str, stage: str) -> None:
    match = VERSION_RE.fullmatch(version)
    if match is None:
        raise ValueError(f"VERSION is not a supported release version: {version}")

    prerelease_stage = match.group("stage")
    if stage == "stable":
        if prerelease_stage is not None:
            raise ValueError("stable evidence requires a VERSION without prerelease suffix")
        return
    if prerelease_stage != stage:
        raise ValueError(
            f"{stage} evidence requires a VERSION with -{stage}.N suffix"
        )


def load_json_object(path: Path, *, artifact_kind: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{artifact_kind} artifact must be valid UTF-8 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{artifact_kind} artifact must contain a JSON object")
    return value


def validate_data_accuracy(path: Path) -> None:
    report = load_json_object(path, artifact_kind="data_accuracy")
    if report.get("schema_version") != 1:
        raise ValueError("data_accuracy artifact must use schema_version=1")
    if report.get("status") != "pass":
        raise ValueError("data_accuracy artifact must report status=pass")
    if not isinstance(report.get("period_count"), int) or report["period_count"] <= 0:
        raise ValueError("data_accuracy artifact must contain at least one period")
    if not isinstance(report.get("metric_count"), int) or report["metric_count"] <= 0:
        raise ValueError("data_accuracy artifact must contain at least one metric")
    for field in ("input_sha256", "policy_sha256"):
        value = str(report.get(field) or "")
        if SHA256_RE.fullmatch(value) is None:
            raise ValueError(f"data_accuracy artifact must contain a valid {field}")


def validate_artifact(kind: str, path: Path) -> int:
    if not path.is_file():
        raise ValueError(f"artifact does not exist: {path}")
    size = path.stat().st_size
    if size <= 0:
        raise ValueError(f"artifact must not be empty: {path}")
    if kind == "data_accuracy":
        validate_data_accuracy(path)
    return size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=sorted(REQUIRED), required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--version-file", type=Path, default=Path("VERSION"))
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    environment = args.environment.strip()
    commit = args.commit.strip()
    if not environment:
        print("release_evidence_error=environment must be non-empty", file=sys.stderr)
        return 2
    if SHA40_RE.fullmatch(commit) is None:
        print("release_evidence_error=commit must be a full 40-character Git SHA", file=sys.stderr)
        return 2

    try:
        version = args.version_file.read_text(encoding="utf-8").strip()
        validate_version_for_stage(version, args.stage)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"release_evidence_error={exc}", file=sys.stderr)
        return 2
    if not version:
        print("release_evidence_error=VERSION is empty", file=sys.stderr)
        return 2

    artifacts = []
    kinds: set[str] = set()
    try:
        for raw in args.artifact:
            kind, path = parse_artifact(raw)
            if kind in kinds:
                raise ValueError(f"duplicate artifact kind: {kind}")
            size = validate_artifact(kind, path)
            kinds.add(kind)
            artifacts.append(
                {
                    "kind": kind,
                    "file": path.name,
                    "size_bytes": size,
                    "sha256": sha256(path),
                }
            )
    except (OSError, ValueError) as exc:
        print(f"release_evidence_error={exc}", file=sys.stderr)
        return 2

    missing = sorted(REQUIRED[args.stage] - kinds)
    report = {
        "schema_version": 2,
        "stage": args.stage,
        "status": "complete" if not missing else "incomplete",
        "version": version,
        "commit": commit.lower(),
        "environment": environment,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "required_artifact_kinds": sorted(REQUIRED[args.stage]),
        "missing_artifact_kinds": missing,
        "artifacts": sorted(artifacts, key=lambda item: item["kind"]),
    }
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
