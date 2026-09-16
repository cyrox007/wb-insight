#!/usr/bin/env python3
"""Collect exact-head GitHub Actions evidence for a WB Insight release candidate.

The report contains workflow names/run ids/statuses only. GitHub tokens and job logs
are never copied into the evidence artifact.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


REQUIRED_WORKFLOWS = (
    "Backend security",
    "Frontend build",
    "Database migrations",
    "Release integrity",
    "Release smoke contract",
    "Systemd updater",
)
SHA40_RE = re.compile(r"^[0-9a-fA-F]{40}$")


class CIAcceptanceError(RuntimeError):
    pass


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CIAcceptanceError(f"unable to read workflow-runs JSON: {path}") from exc
    if not isinstance(value, dict):
        raise CIAcceptanceError("workflow-runs JSON must contain an object")
    return value


def _fetch_runs(repository: str, commit: str, token: str | None) -> dict:
    query = urlencode({"head_sha": commit, "per_page": 100})
    url = f"https://api.github.com/repos/{repository}/actions/runs?{query}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "wb-insight-ci-acceptance",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=30) as response:
            payload = response.read()
    except HTTPError as exc:
        raise CIAcceptanceError(f"GitHub Actions API returned HTTP {exc.code}") from exc
    except URLError as exc:
        raise CIAcceptanceError("GitHub Actions API is unavailable") from exc
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CIAcceptanceError("GitHub Actions API returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise CIAcceptanceError("GitHub Actions API returned an invalid payload")
    return value


def _select_successful_runs(payload: dict, commit: str) -> tuple[dict[str, dict], list[str]]:
    runs = payload.get("workflow_runs")
    if not isinstance(runs, list):
        raise CIAcceptanceError("workflow-runs payload is missing workflow_runs")

    by_name: dict[str, list[dict]] = {}
    for run in runs:
        if not isinstance(run, dict):
            continue
        if str(run.get("head_sha") or "").lower() != commit.lower():
            continue
        name = str(run.get("name") or "").strip()
        if name:
            by_name.setdefault(name, []).append(run)

    selected: dict[str, dict] = {}
    failures: list[str] = []
    for name in REQUIRED_WORKFLOWS:
        candidates = by_name.get(name, [])
        candidates.sort(key=lambda item: int(item.get("run_attempt") or 0), reverse=True)
        success = next(
            (
                item
                for item in candidates
                if item.get("status") == "completed" and item.get("conclusion") == "success"
            ),
            None,
        )
        if success is None:
            if not candidates:
                failures.append(f"{name}:missing")
            else:
                latest = candidates[0]
                failures.append(
                    f"{name}:{latest.get('status') or 'unknown'}/{latest.get('conclusion') or 'none'}"
                )
            continue
        selected[name] = success
    return selected, failures


def _normalized_run(run: dict) -> dict:
    run_id = run.get("id")
    attempt = run.get("run_attempt")
    if not isinstance(run_id, int) or run_id <= 0:
        raise CIAcceptanceError("workflow run is missing a valid id")
    if not isinstance(attempt, int) or attempt <= 0:
        attempt = 1
    return {
        "id": run_id,
        "run_attempt": attempt,
        "event": str(run.get("event") or "unknown"),
        "status": "completed",
        "conclusion": "success",
    }


def validate_ci_report(
    report: dict,
    *,
    version: str,
    commit: str,
    environment: str,
) -> None:
    if report.get("schema_version") != 1 or report.get("kind") != "ci":
        raise CIAcceptanceError("CI evidence must use schema_version=1 and kind=ci")
    if report.get("status") != "pass":
        raise CIAcceptanceError("CI evidence must report status=pass")
    if report.get("version") != version:
        raise CIAcceptanceError("CI evidence version does not match release VERSION")
    if str(report.get("commit") or "").lower() != commit.lower():
        raise CIAcceptanceError("CI evidence commit does not match release commit")
    if report.get("environment") != environment:
        raise CIAcceptanceError("CI evidence environment does not match release environment")
    if report.get("failures") != []:
        raise CIAcceptanceError("CI evidence contains failed or missing workflows")

    required = report.get("required_workflows")
    if required != list(REQUIRED_WORKFLOWS):
        raise CIAcceptanceError("CI evidence required workflow contract does not match current release contract")
    runs = report.get("workflow_runs")
    if not isinstance(runs, dict):
        raise CIAcceptanceError("CI evidence must contain workflow_runs")
    if set(runs) != set(REQUIRED_WORKFLOWS):
        raise CIAcceptanceError("CI evidence does not contain every required workflow")
    for name in REQUIRED_WORKFLOWS:
        run = runs.get(name)
        if not isinstance(run, dict):
            raise CIAcceptanceError(f"CI evidence for {name} is invalid")
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            raise CIAcceptanceError(f"CI workflow {name} is not completed/success")
        if not isinstance(run.get("id"), int) or run["id"] <= 0:
            raise CIAcceptanceError(f"CI workflow {name} has invalid run id")
        if not isinstance(run.get("run_attempt"), int) or run["run_attempt"] <= 0:
            raise CIAcceptanceError(f"CI workflow {name} has invalid run attempt")


def validate_ci_evidence(
    path: Path,
    *,
    version: str,
    commit: str,
    environment: str,
) -> None:
    validate_ci_report(
        _load_json(path),
        version=version,
        commit=commit,
        environment=environment,
    )


def _write_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fixture(commit: str) -> dict:
    return {
        "workflow_runs": [
            {
                "id": index + 100,
                "name": name,
                "head_sha": commit,
                "status": "completed",
                "conclusion": "success",
                "run_attempt": 1,
                "event": "pull_request",
            }
            for index, name in enumerate(REQUIRED_WORKFLOWS)
        ]
    }


def _self_test() -> None:
    commit = "0123456789abcdef0123456789abcdef01234567"
    version = "0.9.0-beta.1"
    environment = "staging-ci-fixture"
    selected, failures = _select_successful_runs(_fixture(commit), commit)
    assert not failures
    assert set(selected) == set(REQUIRED_WORKFLOWS)
    report = {
        "schema_version": 1,
        "kind": "ci",
        "status": "pass",
        "repository": "cyrox007/wb-insight",
        "version": version,
        "commit": commit,
        "environment": environment,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "required_workflows": list(REQUIRED_WORKFLOWS),
        "workflow_runs": {name: _normalized_run(selected[name]) for name in REQUIRED_WORKFLOWS},
        "failures": [],
    }
    validate_ci_report(report, version=version, commit=commit, environment=environment)

    broken = _fixture(commit)
    broken["workflow_runs"][0]["conclusion"] = "failure"
    _, failures = _select_successful_runs(broken, commit)
    assert failures and failures[0].startswith("Backend security:")

    broken_report = dict(report)
    broken_report["workflow_runs"] = dict(report["workflow_runs"])
    broken_report["workflow_runs"].pop("Frontend build")
    try:
        validate_ci_report(
            broken_report,
            version=version,
            commit=commit,
            environment=environment,
        )
    except CIAcceptanceError:
        pass
    else:
        raise AssertionError("incomplete CI evidence unexpectedly passed")
    print("[ok] CI acceptance self-test")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.getenv("GITHUB_REPOSITORY", "cyrox007/wb-insight"))
    parser.add_argument("--commit", default=os.getenv("RELEASE_SHA"))
    parser.add_argument("--version-file", type=Path, default=Path("VERSION"))
    parser.add_argument("--environment", default=os.getenv("ACCEPTANCE_ENVIRONMENT"))
    parser.add_argument("--runs-json", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return 0

    repository = str(args.repository or "").strip()
    commit = str(args.commit or "").strip()
    environment = str(args.environment or "").strip()
    if "/" not in repository or repository.startswith("/") or repository.endswith("/"):
        raise CIAcceptanceError("--repository must use owner/name")
    if SHA40_RE.fullmatch(commit) is None:
        raise CIAcceptanceError("--commit or RELEASE_SHA must be a full 40-character Git SHA")
    if not environment:
        raise CIAcceptanceError("--environment or ACCEPTANCE_ENVIRONMENT is required")
    if args.output is None:
        raise CIAcceptanceError("--output is required")
    try:
        version = args.version_file.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError) as exc:
        raise CIAcceptanceError("unable to read VERSION") from exc
    if not version:
        raise CIAcceptanceError("VERSION is empty")

    payload = (
        _load_json(args.runs_json)
        if args.runs_json is not None
        else _fetch_runs(repository, commit, os.getenv("GITHUB_TOKEN"))
    )
    selected, failures = _select_successful_runs(payload, commit)
    status = "pass" if not failures else "fail"
    report = {
        "schema_version": 1,
        "kind": "ci",
        "status": status,
        "repository": repository,
        "version": version,
        "commit": commit.lower(),
        "environment": environment,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "required_workflows": list(REQUIRED_WORKFLOWS),
        "workflow_runs": {
            name: _normalized_run(selected[name])
            for name in REQUIRED_WORKFLOWS
            if name in selected
        },
        "failures": failures,
    }
    _write_report(args.output, report)
    if failures:
        print("[failed] exact-head CI gates are incomplete or not green", file=sys.stderr)
        return 1
    validate_ci_report(report, version=version, commit=commit, environment=environment)
    print(f"[ok] structured CI evidence: {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except CIAcceptanceError as exc:
        print(f"[failed] {exc}", file=sys.stderr)
        raise SystemExit(1)
