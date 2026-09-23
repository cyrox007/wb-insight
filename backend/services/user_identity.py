"""Канонизация пользовательских идентификаторов для auth и админских сценариев."""

from models.users_model import EntityType


def normalize_email(value) -> str | None:
    """Возвращает канонический email или None для некорректного значения."""
    if not isinstance(value, str):
        return None
    email = value.strip()
    if not email or len(email) > 254 or " " in email or email.count("@") != 1:
        return None
    local_part, domain = email.split("@", 1)
    if (
        not local_part
        or "." not in domain
        or domain.startswith(".")
        or domain.endswith(".")
    ):
        return None
    return email.lower()


def normalize_phone(value) -> str | None:
    """Возвращает российский телефон в формате +7XXXXXXXXXX."""
    if not isinstance(value, str):
        return None
    digits = "".join(char for char in value if char.isdigit())
    if len(digits) == 11 and digits[0] in {"7", "8"}:
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return f"+7{digits}"


def normalize_inn(value) -> str | None:
    """Возвращает ИНН без внешних пробелов или None."""
    if not isinstance(value, str):
        return None
    inn = value.strip()
    if not inn.isdigit() or len(inn) not in {10, 12}:
        return None
    return inn


def normalize_kpp(value) -> str | None:
    """Возвращает девятизначный КПП или None."""
    if not isinstance(value, str):
        return None
    kpp = value.strip()
    if not kpp.isdigit() or len(kpp) != 9:
        return None
    return kpp


def validate_legal_identity(
    *,
    entity_type: str,
    inn_value,
    kpp_value,
    legal_address_value,
) -> dict:
    """Проверяет и канонизирует юридические поля пользовательской identity."""
    normalized_entity_type = str(entity_type or "").strip().lower()
    allowed_entity_types = {item.value for item in EntityType}
    if normalized_entity_type not in allowed_entity_types:
        raise ValueError("Неизвестный тип аккаунта")

    raw_inn = inn_value
    inn = None
    if raw_inn is not None and raw_inn != "":
        inn = normalize_inn(raw_inn)
        expected_length = (
            10
            if normalized_entity_type == EntityType.LEGAL_ENTITY.value
            else 12
        )
        if inn is None or len(inn) != expected_length:
            raise ValueError(
                "ИНН юридического лица должен содержать 10 цифр"
                if normalized_entity_type == EntityType.LEGAL_ENTITY.value
                else "ИНН физического лица или ИП должен содержать 12 цифр"
            )

    if normalized_entity_type == EntityType.LEGAL_ENTITY.value and not inn:
        raise ValueError("ИНН обязателен для юридического лица")

    raw_kpp = kpp_value
    kpp = None
    if raw_kpp is not None and raw_kpp != "":
        kpp = normalize_kpp(raw_kpp)
        if kpp is None:
            raise ValueError("КПП должен содержать 9 цифр")

    legal_address = (
        legal_address_value.strip()
        if isinstance(legal_address_value, str) and legal_address_value.strip()
        else None
    )
    if normalized_entity_type == EntityType.LEGAL_ENTITY.value and not legal_address:
        raise ValueError("Юридический адрес обязателен для юридического лица")

    return {
        "entity_type": normalized_entity_type,
        "inn": inn,
        "kpp": kpp,
        "legal_address": legal_address,
    }
