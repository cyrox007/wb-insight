import base64
import json
from datetime import datetime, timedelta, timezone

import pytest

from integrations.wildberries.token_metadata import (
    WBTokenValidationError,
    decode_wb_token,
    validate_analytics_permissions,
    validate_cloud_service_token,
)


NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)
REQUIRED_BITS = (1, 2, 3, 5, 6, 13, 30)


def permission_mask(*bits: int) -> int:
    return sum(1 << bit for bit in bits)


def make_token(payload: dict) -> str:
    def encode(value: dict) -> str:
        raw = json.dumps(value, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    header = {"alg": "none", "typ": "JWT"}
    return f"{encode(header)}.{encode(payload)}.signature"


def future_exp(days: int = 30) -> int:
    return int((NOW + timedelta(days=days)).timestamp())


def test_base_token_metadata_and_permissions_come_from_jwt_claims():
    token = make_token(
        {
            "acc": 1,
            "exp": future_exp(),
            "id": "token-id",
            "sid": 123456,
            "s": permission_mask(*REQUIRED_BITS),
            "t": False,
        }
    )

    metadata = decode_wb_token(token, now=NOW)

    assert metadata.token_type == "base"
    assert metadata.expires_at == NOW + timedelta(days=30)
    assert metadata.token_id == "token-id"
    assert metadata.seller_id == "123456"
    assert metadata.permissions_mask == permission_mask(*REQUIRED_BITS)
    assert metadata.service_id is None
    validate_cloud_service_token(metadata, service_id=None)
    validate_analytics_permissions(metadata)


def test_missing_required_category_is_rejected():
    metadata = decode_wb_token(
        make_token(
            {
                "acc": 1,
                "exp": future_exp(),
                "s": permission_mask(1, 2, 3, 5, 13, 30),
                "t": False,
            }
        ),
        now=NOW,
    )

    with pytest.raises(WBTokenValidationError) as exc_info:
        validate_analytics_permissions(metadata)

    assert exc_info.value.code == "WB_TOKEN_PERMISSIONS_MISSING"
    assert "Продвижение" in str(exc_info.value)


def test_write_enabled_token_is_rejected():
    metadata = decode_wb_token(
        make_token(
            {
                "acc": 1,
                "exp": future_exp(),
                "s": permission_mask(1, 2, 3, 5, 6, 13),
                "t": False,
            }
        ),
        now=NOW,
    )

    with pytest.raises(WBTokenValidationError) as exc_info:
        validate_analytics_permissions(metadata)

    assert exc_info.value.code == "WB_TOKEN_MUST_BE_READ_ONLY"


def test_personal_token_is_rejected_for_cloud_service():
    metadata = decode_wb_token(
        make_token(
            {
                "acc": 3,
                "exp": future_exp(),
                "for": "self",
                "t": False,
            }
        ),
        now=NOW,
    )

    with pytest.raises(WBTokenValidationError) as exc_info:
        validate_cloud_service_token(metadata, service_id=None)

    assert exc_info.value.code == "WB_PERSONAL_TOKEN_NOT_ALLOWED"


def test_test_token_is_rejected_for_production_integration():
    metadata = decode_wb_token(
        make_token(
            {
                "acc": 2,
                "exp": future_exp(),
                "t": True,
            }
        ),
        now=NOW,
    )

    with pytest.raises(WBTokenValidationError) as exc_info:
        validate_cloud_service_token(metadata, service_id=None)

    assert exc_info.value.code == "WB_TEST_TOKEN_NOT_SUPPORTED"


def test_service_token_requires_matching_asid_and_service_secret():
    metadata = decode_wb_token(
        make_token(
            {
                "acc": 4,
                "exp": future_exp(),
                "for": "asid:service-42",
                "t": False,
            }
        ),
        now=NOW,
    )

    validate_cloud_service_token(
        metadata,
        service_id="service-42",
        service_secret_configured=True,
    )

    with pytest.raises(WBTokenValidationError) as exc_info:
        validate_cloud_service_token(
            metadata,
            service_id="another-service",
            service_secret_configured=True,
        )

    assert exc_info.value.code == "WB_SERVICE_TOKEN_MISMATCH"


def test_service_token_requires_configured_service_identity():
    metadata = decode_wb_token(
        make_token(
            {
                "acc": 4,
                "exp": future_exp(),
                "for": "asid:service-42",
                "t": False,
            }
        ),
        now=NOW,
    )

    with pytest.raises(WBTokenValidationError) as exc_info:
        validate_cloud_service_token(metadata, service_id=None)

    assert exc_info.value.code == "WB_SERVICE_ID_NOT_CONFIGURED"


def test_service_token_requires_configured_service_secret():
    metadata = decode_wb_token(
        make_token(
            {
                "acc": 4,
                "exp": future_exp(),
                "for": "asid:service-42",
                "t": False,
            }
        ),
        now=NOW,
    )

    with pytest.raises(WBTokenValidationError) as exc_info:
        validate_cloud_service_token(
            metadata,
            service_id="service-42",
            service_secret_configured=False,
        )

    assert exc_info.value.code == "WB_SERVICE_SECRET_NOT_CONFIGURED"
    assert exc_info.value.status_code == 503


def test_expired_token_is_rejected_from_real_exp_claim():
    token = make_token(
        {
            "acc": 1,
            "exp": int((NOW - timedelta(seconds=1)).timestamp()),
            "t": False,
        }
    )

    with pytest.raises(WBTokenValidationError) as exc_info:
        decode_wb_token(token, now=NOW)

    assert exc_info.value.code == "WB_TOKEN_EXPIRED"


@pytest.mark.parametrize(
    "token",
    [
        "",
        "not-a-jwt",
        "one.two",
        "one.two.three.four",
        "header.@@@.signature",
    ],
)
def test_malformed_token_is_rejected(token):
    with pytest.raises(WBTokenValidationError) as exc_info:
        decode_wb_token(token, now=NOW)

    assert exc_info.value.code == "WB_TOKEN_MALFORMED"
