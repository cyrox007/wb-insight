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


def _required_value(metric: dict[str, Any], policy: dict[str, Any], metric_id: str) -> bool:
    policy_required = bool(policy.get("required", True))
    if "required" not in metric:
        return policy_required

    requested = metric["required"]
    if not isinstance(requested, bool):
        raise AcceptanceError(f"{metric_id}.required must be boolean")
    if policy_required and requested is False:
        raise AcceptanceError(
            f"{metric_id}.required cannot disable a policy-required metric"
        )
    return policy_required or requested


def _effective_tolerances(
    metric: dict[str, Any],
    policy: dict[str, Any],
    metric_id: str,
) -> tuple[str, Decimal, Decimal, str | None]:
    policy_mode = str(policy.get("tolerance_mode", "absolute")).strip().lower()
    mode = str(metric.get("tolerance_mode", policy_mode)).strip().lower()

    policy_absolute = as_decimal(
        policy.get("absolute_tolerance", "0"),
        f"{metric_id}.policy.absolute_tolerance",
    )
    absolute_tolerance = as_decimal(
        metric.get("absolute_tolerance", policy_absolute),
        f"{metric_id}.absolute_tolerance",
    )
    policy_relative = as_decimal(
        policy.get("relative_tolerance_percent", "0"),
        f"{metric_id}.policy.relative_tolerance_percent",
    )
    relative_tolerance = as_decimal(
        metric.get("relative_tolerance_percent", policy_relative),
        f"{metric_id}.relative_tolerance_percent",
    )

    overridden = (
        mode != policy_mode
        or absolute_tolerance != policy_absolute
        or relative_tolerance != policy_relative
    )
    reason_raw = metric.get("override_reason")
    override_reason = str(reason_raw).strip() if reason_raw is not None else None
    if overridden and not override_reason:
        raise AcceptanceError(
            f"{metric_id}.override_reason is required when tolerance overrides policy"
        )

    return mode, absolute_tolerance, relative_tolerance, override_reason if overridden else None


def evaluate_metric(metric: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    metric_id = str(metric.get("metric", "")).strip()
    source = str(metric.get("source", "")).strip()
    if not metric_id or not source:
        raise AcceptanceError("metric and source are required")

    required = _required_value(metric, policy, metric_id)
    expected_raw = metric.get("expected")
    actual_raw = metric.get("actual")
    if expected_raw is None or actual_raw is None:
        return {
            "metric": metric_id,
            "source": source,
            "required": required,
            "status": "missing" if required else "skipped",
            "unit": policy.get("unit"),
            "category": policy.get("category"),
        }

    expected = as_decimal(expected_raw, f"{metric_id}.expected")
    actual = as_decimal(actual_raw, f"{metric_id}.actual")
    absolute_diff = abs(actual - expected)
    relative_diff = None if expected == 0 else absolute_diff / abs(expected) * Decimal("100")
    mode, absolute_tolerance, relative_tolerance, override_reason = _effective_tolerances(
        metric,
        policy,
        metric_id,
    )

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
        "override_reason": override_reason,
        "unit": policy.get("unit"),
        "category": policy.get("category"),
    }
