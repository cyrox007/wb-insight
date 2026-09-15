import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


class WBTokenValidationError(ValueError):
    """User-safe validation error for Wildberries credential metadata."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class WBTokenMetadata:
    token_type: str
    expires_at: datetime
    token_id: str | None
    seller_id: str | None
    permissions_mask: int | None
    service_id: str | None
    is_test: bool


_TOKEN_TYPES = {
    1: "base",
    2: "test",
    3: "personal",
    4: "service",
}


def _malformed(message: str = "Некорректный формат токена Wildberries") -> WBTokenValidationError:
    return WBTokenValidationError("WB_TOKEN_MALFORMED", message)


def _decode_payload_segment(segment: str) -> dict[str, Any]:
    padding = "=" * (-len(segment) % 4)
    try:
        raw = base64.urlsafe_b64decode((segment + padding).encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeEncodeError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise _malformed() from exc

    if not isinstance(payload, dict):
        raise _malformed()
    return payload


def _as_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise _malformed(f"Некорректное поле {field} в токене Wildberries")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise _malformed(f"Некорректное поле {field} в токене Wildberries") from exc


def decode_wb_token(
    raw_token: str,
    *,
    now: datetime | None = None,
) -> WBTokenMetadata:
    """
    Decode WB JWT metadata without trusting it as authentication proof.

    Wildberries validates the token cryptographically when it is used against
    the marketplace API. Here we only read documented claims so the application
    can enforce cloud-service token policy before storing the credential.
    """

    token = raw_token.strip()
    parts = token.split(".")
    if len(parts) != 3 or any(not part for part in parts):
        raise _malformed()

    payload = _decode_payload_segment(parts[1])

    account_type = _as_int(payload.get("acc"), "acc")
    token_type = _TOKEN_TYPES.get(account_type)
    if token_type is None:
        raise WBTokenValidationError(
            "WB_TOKEN_UNSUPPORTED_TYPE",
            "Wildberries вернул неподдерживаемый тип токена",
        )

    expires_timestamp = _as_int(payload.get("exp"), "exp")
    try:
        expires_at = datetime.fromtimestamp(expires_timestamp, tz=timezone.utc)
    except (OverflowError, OSError, ValueError) as exc:
        raise _malformed("Некорректный срок действия токена Wildberries") from exc

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    if expires_at <= current_time:
        raise WBTokenValidationError(
            "WB_TOKEN_EXPIRED",
            "Срок действия токена Wildberries истёк",
        )

    target = payload.get("for")
    service_id: str | None = None
    if token_type == "service":
        if (
            not isinstance(target, str)
            or not target.startswith("asid:")
            or not target.removeprefix("asid:")
        ):
            raise _malformed(
                "Сервисный токен Wildberries не содержит корректный asid"
            )
        service_id = target.removeprefix("asid:")
    elif token_type == "personal" and target not in (None, "self"):
        raise _malformed(
            "Персональный токен Wildberries содержит некорректное поле for"
        )

    test_claim = payload.get("t")
    if token_type == "test" and test_claim is False:
        raise _malformed(
            "Тестовый токен Wildberries содержит противоречивые метаданные"
        )
    if token_type != "test" and test_claim is True:
        raise _malformed(
            "Токен Wildberries содержит противоречивые метаданные"
        )

    permissions_mask = None
    if payload.get("s") is not None:
        permissions_mask = _as_int(payload.get("s"), "s")

    return WBTokenMetadata(
        token_type=token_type,
        expires_at=expires_at,
        token_id=str(payload["id"]) if payload.get("id") is not None else None,
        seller_id=str(payload["sid"]) if payload.get("sid") is not None else None,
        permissions_mask=permissions_mask,
        service_id=service_id,
        is_test=token_type == "test",
    )


def validate_cloud_service_token(
    metadata: WBTokenMetadata,
    *,
    service_id: str | None,
) -> None:
    """Enforce the WB token types permitted for this production cloud service."""

    if metadata.token_type == "base":
        return

    if metadata.token_type == "personal":
        raise WBTokenValidationError(
            "WB_PERSONAL_TOKEN_NOT_ALLOWED",
            (
                "Персональный токен нельзя использовать в облачном сервисе. "
                "Создайте базовый токен Wildberries."
            ),
        )

    if metadata.token_type == "test":
        raise WBTokenValidationError(
            "WB_TEST_TOKEN_NOT_SUPPORTED",
            (
                "Тестовый токен Wildberries предназначен для тестового контура "
                "и не поддерживается этой интеграцией."
            ),
        )

    if metadata.token_type == "service":
        expected_service_id = (service_id or "").strip()
        if not expected_service_id:
            raise WBTokenValidationError(
                "WB_SERVICE_ID_NOT_CONFIGURED",
                (
                    "Сервисный токен можно подключить после настройки WB_SERVICE_ID. "
                    "До этого используйте базовый токен Wildberries."
                ),
            )

        if metadata.service_id != expected_service_id:
            raise WBTokenValidationError(
                "WB_SERVICE_TOKEN_MISMATCH",
                "Сервисный токен выпущен для другого сервиса Wildberries.",
            )
        return

    raise WBTokenValidationError(
        "WB_TOKEN_UNSUPPORTED_TYPE",
        "Неподдерживаемый тип токена Wildberries",
    )
