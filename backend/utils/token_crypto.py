import base64
import hashlib
from typing import cast

from cryptography.fernet import Fernet, InvalidToken

from settings import config


class TokenDecryptionError(ValueError):
    """Безопасная внутренняя ошибка расшифровки сохранённого токена."""


MASTER_KEY_RAW = config.ENCRYPTION_KEY

if MASTER_KEY_RAW is None:
    raise ValueError(
        "Переменная окружения API_TOKEN_ENCRYPTION_KEY не установлена. "
        "Сгенерируйте ключ командой: python -c "
        "\"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )

MASTER_KEY = cast(str, MASTER_KEY_RAW)


def _get_user_key(user_id: str) -> Fernet:
    """Создаёт отдельный ключ Fernet из мастер-ключа и идентификатора пользователя."""

    base_key = MASTER_KEY.encode()
    derived = hashlib.sha256(base_key + user_id.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(derived)
    return Fernet(fernet_key)


def _get_legacy_key() -> Fernet:
    """Возвращает исторический Fernet-ключ, использовавшийся до 30 апреля 2026 года."""

    try:
        return Fernet(MASTER_KEY.encode())
    except (TypeError, ValueError) as exc:
        raise TokenDecryptionError(
            "Исторический формат ключа шифрования недоступен"
        ) from exc


def encrypt_token(token: str, user_id: str) -> str:
    """Шифрует токен отдельным ключом пользователя."""

    fernet = _get_user_key(user_id)
    return fernet.encrypt(token.encode()).decode()


def decrypt_token_with_legacy_status(
    encrypted_token: str,
    user_id: str,
) -> tuple[str, bool]:
    """
    Расшифровывает токен новой схемой и при необходимости историческим ключом.

    Второе возвращаемое значение равно True, когда использован исторический
    формат. Это позволяет безопасно перешифровать запись после проверки.
    """

    payload = encrypted_token.encode()
    try:
        raw = _get_user_key(user_id).decrypt(payload)
        return raw.decode(), False
    except (InvalidToken, UnicodeDecodeError):
        pass

    try:
        raw = _get_legacy_key().decrypt(payload)
        return raw.decode(), True
    except (InvalidToken, UnicodeDecodeError, TokenDecryptionError) as exc:
        raise TokenDecryptionError(
            "Сохранённый токен не удалось расшифровать"
        ) from exc


def decrypt_token(encrypted_token: str, user_id: str) -> str:
    """Расшифровывает токен с поддержкой текущего и исторического формата."""

    raw_token, _used_legacy = decrypt_token_with_legacy_status(
        encrypted_token,
        user_id,
    )
    return raw_token
