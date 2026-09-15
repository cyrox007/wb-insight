#!/usr/bin/env python3
"""WB Insight data accuracy acceptance runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from acceptance.data_accuracy import AcceptanceError, evaluate_metric


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AcceptanceError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AcceptanceError(f"{path} must contain a JSON object")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evaluate(data: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    dataset_id = str(data.get("dataset_id", "")).strip()
    seller_alias = str(data.get("seller_alias", "")).strip()
    periods = data.get("periods")
    policies = policy.get("metrics")
    if not dataset_id or not seller_alias:
        raise AcceptanceError("dataset_id and seller_alias are required")
    if not isinstance(periods, list) or not periods:
        raise AcceptanceError("periods must be a non-empty list")
    if not isinstance(policies, dict):
        raise AcceptanceError("policy.metrics must be an object")

    rows: list[dict[str, Any]] = []
    seen_periods: set[str] = set()
    for period in periods:
        if not isinstance(period, dict):
            raise AcceptanceError("every period must be an object")
        label = str(period.get("label", "")).strip()
        start_date = str(period.get("start_date", "")).strip()
        end_date = str(period.get("end_date", "")).strip()
        metrics = period.get("metrics")
        if not label or not start_date or not end_date:
            raise AcceptanceError("period label, start_date and end_date are required")
        if label in seen_periods:
            raise AcceptanceError(f"duplicate period: {label}")
        seen_periods.add(label)
        if not isinstance(metrics, list) or not metrics:
            raise AcceptanceError(f"period {label} has no metrics")

        seen_metrics: set[str] = set()
        for metric in metrics:
            if not isinstance(metric, dict):
                raise AcceptanceError(f"period {label} contains a non-object metric")
            metric_id = str(metric.get("metric", "")).strip()
            if metric_id in seen_metrics:
                raise AcceptanceError(f"duplicate metric {metric_id} in {label}")
            seen_metrics.add(metric_id)
            metric_policy = policies.get(metric_id)
            if not isinstance(metric_policy, dict):
                raise AcceptanceError(f"metric {metric_id} is absent from policy")
            row = evaluate_metric(metric, metric_policy)
            row.update({"period": label, "start_date": start_date, "end_date": end_date})
            rows.append(row)

    counts = {status: 0 for status in ("pass", "fail", "missing", "skipped")}
    for row in rows:
        counts[row["status"]] += 1
    status = "pass" if counts["fail"] == 0 and counts["missing"] == 0 else "fail"
    return {
        "schema_version": 1,
        "status": status,
        "dataset_id": dataset_id,
        "seller_alias": seller_alias,
        "policy_version": str(policy.get("policy_version", "unknown")),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "period_count": len(periods),
        "metric_count": len(rows),
        "counts": counts,
        "results": rows,
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# WB Insight — data accuracy acceptance",
        "",
        f"- Status: **{report['status']}**",
        f"- Dataset: `{report['dataset_id']}`",
        f"- Seller alias: `{report['seller_alias']}`",
        f"- Policy: `{report['policy_version']}`",
        f"- Evaluated: `{report['evaluated_at']}`",
        "",
        "| Period | Metric | Expected | Actual | Abs diff | Status | Source |",
        "|---|---|---:|---:|---:|---|---|",
    ]
    for row in report["results"]:
        lines.append(
            "| {period} | {metric} | {expected} | {actual} | {diff} | {status} | {source} |".format(
                period=row["period"],
                metric=row["metric"],
                expected=row.get("expected", "—"),
                actual=row.get("actual", "—"),
                diff=row.get("absolute_diff", "—"),
                status=row["status"],
                source=str(row["source"]).replace("|", "/"),
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path(__file__).with_name("acceptance") / "wb_v1_metric_policy.json",
    )
    parser.add_argument("--output-json", type=Path)
    parser.add_argument("--output-md", type=Path)
    args = parser.parse_args()

    try:
        report = evaluate(load_json(args.input), load_json(args.policy))
        report["input_sha256"] = file_sha256(args.input)
        report["policy_sha256"] = file_sha256(args.policy)
    except AcceptanceError as exc:
        print(f"data_accuracy_error={exc}", file=sys.stderr)
        return 2

    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(markdown(report), encoding="utf-8")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
