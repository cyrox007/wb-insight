import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


class WBTokenValidationError(ValueError):
    """Безопасная для пользователя ошибка проверки метаданных токена Wildberries."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


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

# Текущий набор API Wildberries используется WB Insight только для чтения.
# Позиции битов определены Wildberries в маске разрешений JWT `s`. Перед
# добавлением новой категории API этот список нужно синхронизировать
# с фактическими обработчиками загрузки.
WB_ANALYTICS_REQUIRED_PERMISSIONS: tuple[tuple[int, str], ...] = (
    (1, "Контент"),
    (2, "Аналитика"),
    (3, "Цены и скидки"),
    (5, "Статистика"),
    (6, "Продвижение"),
    (13, "Финансы"),
)
WB_READ_ONLY_PERMISSION_BIT = 30


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


def _has_permission(mask: int, bit: int) -> bool:
    return bool(mask & (1 << bit))


def decode_wb_token(
    raw_token: str,
    *,
    now: datetime | None = None,
) -> WBTokenMetadata:
    """
    Декодирует документированные метаданные JWT Wildberries без признания токена действующим.

    Полученные поля используются только для локальной проверки политики.
    Отдельный запрос `/ping` должен подтвердить, что токен не отозван и
    принимается Wildberries.
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


def validate_analytics_permissions(metadata: WBTokenMetadata) -> None:
    """Проверяет минимально необходимые категории доступа текущего продукта."""

    mask = metadata.permissions_mask
    if mask is None:
        raise WBTokenValidationError(
            "WB_TOKEN_PERMISSIONS_MISSING",
            "Токен Wildberries не содержит информацию о категориях доступа.",
        )

    missing = [
        name
        for bit, name in WB_ANALYTICS_REQUIRED_PERMISSIONS
        if not _has_permission(mask, bit)
    ]
    if missing:
        raise WBTokenValidationError(
            "WB_TOKEN_PERMISSIONS_MISSING",
            (
                "Для полной аналитики не хватает категорий WB API: "
                + ", ".join(missing)
                + ". Создайте новый токен с этими категориями."
            ),
        )

    if not _has_permission(mask, WB_READ_ONLY_PERMISSION_BIT):
        raise WBTokenValidationError(
            "WB_TOKEN_MUST_BE_READ_ONLY",
            (
                "Для WB Insight нужен токен с уровнем доступа «Только чтение». "
                "Токены с правом изменения данных не принимаются."
            ),
        )


def validate_cloud_service_token(
    metadata: WBTokenMetadata,
    *,
    service_id: str | None,
    service_secret_configured: bool = False,
) -> None:
    """Проверяет политику токена партнёрского сервиса и сервисного секрета Wildberries."""

    if metadata.token_type == "personal":
        raise WBTokenValidationError(
            "WB_PERSONAL_TOKEN_NOT_ALLOWED",
            (
                "Персональный токен нельзя использовать в облачном сервисе. "
                "Создайте базовый или сервисный токен Wildberries."
            ),
        )

    if metadata.token_type == "test":
        raise WBTokenValidationError(
            "WB_TEST_TOKEN_NOT_SUPPORTED",
            (
                "Тестовый токен Wildberries предназначен для тестового контура "
                "и не поддерживается рабочей интеграцией."
            ),
        )

    if metadata.token_type not in {"base", "service"}:
        raise WBTokenValidationError(
            "WB_TOKEN_UNSUPPORTED_TYPE",
            "Неподдерживаемый тип токена Wildberries",
        )

    expected_service_id = (service_id or "").strip()
    if not expected_service_id or not service_secret_configured:
        raise WBTokenValidationError(
            "WB_SERVICE_CREDENTIALS_NOT_CONFIGURED",
            (
                "Подключение кабинетов Wildberries временно недоступно: "
                "на сервере не настроены реквизиты партнёрского сервиса WB."
            ),
            status_code=503,
        )

    if metadata.token_type == "service" and metadata.service_id != expected_service_id:
        raise WBTokenValidationError(
            "WB_SERVICE_TOKEN_MISMATCH",
            "Сервисный токен выпущен для другого сервиса Wildberries.",
        )
