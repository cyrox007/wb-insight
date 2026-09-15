#!/usr/bin/env python3
"""Build and validate a WB Insight release-evidence manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


REQUIRED = {
    "beta": {"ci", "core_smoke", "data_accuracy"},
    "rc": {
        "ci",
        "core_smoke",
        "data_accuracy",
        "wb_full_sync",
        "sber_payment",
        "deployment",
        "operations",
        "backup_restore",
        "legal",
        "account_lifecycle",
    },
    "stable": {
        "ci",
        "core_smoke",
        "data_accuracy",
        "wb_full_sync",
        "sber_payment",
        "deployment",
        "operations",
        "backup_restore",
        "legal",
        "account_lifecycle",
        "rc_signoff",
    },
}


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
    if not kind or not str(path):
        raise ValueError("artifact kind and path must be non-empty")
    return kind, path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=sorted(REQUIRED), required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--version-file", type=Path, default=Path("VERSION"))
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        version = args.version_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
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
            if not path.is_file():
                raise ValueError(f"artifact does not exist: {path}")
            kinds.add(kind)
            artifacts.append(
                {
                    "kind": kind,
                    "file": path.name,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    except (OSError, ValueError) as exc:
        print(f"release_evidence_error={exc}", file=sys.stderr)
        return 2

    missing = sorted(REQUIRED[args.stage] - kinds)
    report = {
        "schema_version": 1,
        "stage": args.stage,
        "status": "complete" if not missing else "incomplete",
        "version": version,
        "commit": args.commit,
        "environment": args.environment,
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
