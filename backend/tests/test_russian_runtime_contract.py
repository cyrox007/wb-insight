from datetime import date
from pathlib import Path

import pytest

from services.dashboard.semantic_metrics import inclusive_days


BACKEND_ROOT = Path(__file__).resolve().parents[1]

RUNTIME_FILES = (
    "core/database.py",
    "core/middleware.py",
    "services/marketplace_access_service.py",
    "services/dashboard/account_scope.py",
    "services/dashboard/semantic_metrics.py",
)

FORBIDDEN_ENGLISH_PHRASES = (
    "Database connection attempt",
    "Failed to connect to database",
    "Unexpected database error",
    "Unexpected control flow",
    "Database health check failed",
    "Database engine disposed",
    "Validate a Bearer access token",
    "Compatibility for development tests",
    "Tariff configuration is the single source",
    "Return only WB tokens allowed",
    "Live-check a stored credential",
    "WB quota live-check",
    "Invalidate confirmed stale WB credentials",
    "Return the effective Wildberries account quota",
    "Requested marketplace account is not available",
    "Resolve dashboard data to the WB accounts",
    "end_date must be on or after start_date",
    "Return actual advertising spend",
)


def test_core_runtime_files_do_not_restore_known_english_system_text():
    combined = "\n".join(
        (BACKEND_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in RUNTIME_FILES
    )

    for phrase in FORBIDDEN_ENGLISH_PHRASES:
        assert phrase not in combined, (
            f"В системном коде снова появился англоязычный текст: {phrase}"
        )


def test_invalid_period_error_is_russian():
    with pytest.raises(
        ValueError,
        match="Дата окончания периода не может быть раньше даты начала",
    ):
        inclusive_days(date(2026, 9, 22), date(2026, 9, 21))
