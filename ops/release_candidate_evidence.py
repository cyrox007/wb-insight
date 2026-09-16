#!/usr/bin/env python3
"""Build a release manifest only after strict CI/runtime evidence validation."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from ci_acceptance import CIAcceptanceError, validate_ci_evidence
from release_evidence import SHA40_RE, parse_artifact, validate_version_for_stage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("beta", "rc", "stable"), required=True)
    parser.add_argument("--environment", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--version-file", type=Path, default=Path("VERSION"))
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    environment = args.environment.strip()
    commit = args.commit.strip()
    if not environment:
        print("release_candidate_error=environment must be non-empty", file=sys.stderr)
        return 2
    if SHA40_RE.fullmatch(commit) is None:
        print("release_candidate_error=commit must be a full 40-character Git SHA", file=sys.stderr)
        return 2
    try:
        version = args.version_file.read_text(encoding="utf-8").strip()
        validate_version_for_stage(version, args.stage)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"release_candidate_error={exc}", file=sys.stderr)
        return 2

    ci_path: Path | None = None
    try:
        for raw in args.artifact:
            kind, path = parse_artifact(raw)
            if kind == "ci":
                if ci_path is not None:
                    raise ValueError("duplicate ci artifact")
                ci_path = path
    except ValueError as exc:
        print(f"release_candidate_error={exc}", file=sys.stderr)
        return 2
    if ci_path is None:
        print("release_candidate_error=structured ci artifact is required", file=sys.stderr)
        return 2

    try:
        validate_ci_evidence(
            ci_path,
            version=version,
            commit=commit,
            environment=environment,
        )
    except CIAcceptanceError as exc:
        print(f"release_candidate_error={exc}", file=sys.stderr)
        return 2

    release_evidence = Path(__file__).resolve().with_name("release_evidence.py")
    command = [
        sys.executable,
        str(release_evidence),
        "--stage",
        args.stage,
        "--environment",
        environment,
        "--commit",
        commit,
        "--version-file",
        str(args.version_file),
        "--require-structured-runtime-evidence",
        "--output",
        str(args.output),
    ]
    for artifact in args.artifact:
        command.extend(["--artifact", artifact])
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        return completed.returncode
    print(f"[ok] strict release candidate evidence manifest: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
