from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from integrations.wildberries.adapter import WildberriesAdapter
from integrations.wildberries.finance_normalizer import normalize_finance_row
from integrations.wildberries.operational_normalizer import normalize_order_row


BACKEND_ROOT = Path(__file__).resolve().parents[1]

WB_INTEGRATION_FILES = (
    "integrations/wildberries/adapter.py",
    "integrations/wildberries/advertising_normalizer.py",
    "integrations/wildberries/client.py",
    "integrations/wildberries/endpoints.py",
    "integrations/wildberries/finance_client.py",
    "integrations/wildberries/finance_normalizer.py",
    "integrations/wildberries/funnel_normalizer.py",
    "integrations/wildberries/operational_normalizer.py",
    "integrations/wildberries/paid_storage_normalizer.py",
    "integrations/wildberries/rate_limit.py",
    "integrations/wildberries/token_metadata.py",
    "integrations/wildberries/token_validation.py",
)

FORBIDDEN_ENGLISH_PHRASES = (
    "Unknown wildberries entity",
    "Flatten WB v3 campaign",
    "Wildberries HTTP client with bounded retry",
    "Wildberries partner service secret is not configured",
    "Wildberries transport error after retry budget was exhausted",
    "WB transport error endpoint",
    "WB authorization rejected endpoint",
    "Wildberries authorization rejected the marketplace credential",
    "WB feature unavailable endpoint",
    "Wildberries feature is unavailable for the current account plan",
    "WB permission denied endpoint",
    "Wildberries credential lacks permission for this API category",
    "Wildberries rate limit retry budget was exhausted",
    "WB rate limited endpoint",
    "Wildberries server error after retry budget was exhausted",
    "WB server error endpoint",
    "WB request rejected endpoint",
    "Wildberries API rejected the request",
    "WB returned invalid JSON endpoint",
    "Wildberries returned an invalid JSON response",
    "Wildberries request failed",
    "Legacy finance endpoint kept only as a historical reference",
    "Current Documents & Accounting API methods",
    "WB finance row is missing required identity fields",
    "Flatten WB Analytics v3 product history",
    "WB operational row is missing required",
    "WB operational row contains invalid datetime",
    "Normalize the current WB Paid Storage report",
    "Coordinate WB request spacing",
    "WB distributed rate limiter unavailable",
    "Publish a cooldown without shortening",
    "Unable to publish WB rate-limit cooldown",
    "User-safe validation error for Wildberries credential metadata",
    "Current WB Insight read-only product surface",
    "Decode documented WB JWT metadata",
    "Require the least-privilege categories",
    "Enforce current WB partner-service token",
    "Verify with WB that a partner-service credential is active",
    "production-интеграцией",
)


def test_wb_integration_does_not_restore_known_english_system_text():
    combined = "\n".join(
        (BACKEND_ROOT / relative_path).read_text(encoding="utf-8")
        for relative_path in WB_INTEGRATION_FILES
    )

    for phrase in FORBIDDEN_ENGLISH_PHRASES:
        assert phrase not in combined, (
            f"В интеграции Wildberries снова появился англоязычный текст: {phrase}"
        )


@pytest.mark.asyncio
async def test_unknown_wb_entity_error_is_russian():
    adapter = WildberriesAdapter()

    with pytest.raises(ValueError, match="Неизвестная сущность wildberries"):
        await adapter.sync_entity(
            object(),
            SimpleNamespace(entity="unknown_entity"),
            object(),
        )


def test_finance_normalizer_identity_error_is_russian():
    with pytest.raises(
        ValueError,
        match="В финансовой строке Wildberries отсутствуют обязательные идентификаторы",
    ):
        normalize_finance_row({}, uuid4(), uuid4())


def test_operational_normalizer_required_field_error_is_russian():
    with pytest.raises(
        ValueError,
        match="В операционной строке Wildberries отсутствует обязательное поле: srid",
    ):
        normalize_order_row({}, uuid4(), uuid4())
