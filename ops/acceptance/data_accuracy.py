from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any


class AcceptanceError(ValueError):
    pass


def as_decimal(value: Any, field: str) -> Decimal:
    if value is None or isinstance(value, bool):
        raise AcceptanceError(f"{field} must be numeric")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise AcceptanceError(f"{field} must be numeric") from exc


def decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else format(value.normalize(), "f")


def evaluate_metric(metric: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    metric_id = str(metric.get("metric", "")).strip()
    source = str(metric.get("source", "")).strip()
    if not metric_id or not source:
        raise AcceptanceError("metric and source are required")

    required = bool(metric.get("required", policy.get("required", True)))
    expected_raw = metric.get("expected")
    actual_raw = metric.get("actual")
    if expected_raw is None or actual_raw is None:
        return {
            "metric": metric_id,
            "source": source,
            "required": required,
            "status": "missing" if required else "skipped",
        }

    expected = as_decimal(expected_raw, f"{metric_id}.expected")
    actual = as_decimal(actual_raw, f"{metric_id}.actual")
    absolute_diff = abs(actual - expected)
    relative_diff = None if expected == 0 else absolute_diff / abs(expected) * Decimal("100")
    absolute_tolerance = as_decimal(
        metric.get("absolute_tolerance", policy.get("absolute_tolerance", "0")),
        f"{metric_id}.absolute_tolerance",
    )
    relative_tolerance = as_decimal(
        metric.get("relative_tolerance_percent", policy.get("relative_tolerance_percent", "0")),
        f"{metric_id}.relative_tolerance_percent",
    )
    mode = str(metric.get("tolerance_mode", policy.get("tolerance_mode", "absolute"))).lower()

    absolute_ok = absolute_diff <= absolute_tolerance
    relative_ok = relative_diff is not None and relative_diff <= relative_tolerance
    if mode == "absolute":
        passed = absolute_ok
    elif mode == "relative":
        passed = relative_ok
    elif mode == "either":
        passed = absolute_ok or relative_ok
    elif mode == "both":
        passed = absolute_ok and relative_ok
    else:
        raise AcceptanceError(f"unsupported tolerance_mode: {mode}")

    return {
        "metric": metric_id,
        "source": source,
        "required": required,
        "status": "pass" if passed else "fail",
        "expected": decimal_text(expected),
        "actual": decimal_text(actual),
        "absolute_diff": decimal_text(absolute_diff),
        "relative_diff_percent": decimal_text(relative_diff),
        "tolerance_mode": mode,
        "absolute_tolerance": decimal_text(absolute_tolerance),
        "relative_tolerance_percent": decimal_text(relative_tolerance),
        "unit": policy.get("unit"),
        "category": policy.get("category"),
    }
