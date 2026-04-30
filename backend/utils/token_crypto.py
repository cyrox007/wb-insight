import base64
import hashlib
from typing import cast

from cryptography.fernet import Fernet

from settings import config

MASTER_KEY_RAW = config.ENCRYPTION_KEY

if MASTER_KEY_RAW is None:
    raise ValueError(
        "Переменная окружения API_TOKEN_ENCRYPTION_KEY не установлена. "
        "Сгенерируйте ключ командой: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )

# Явно приводим тип к str, чтобы линтер понял, что ниже это точно строка
MASTER_KEY = cast(str, MASTER_KEY_RAW)

def _get_user_key(user_id: str) -> Fernet:
    """
    Derives a unique encryption key for each user based on master key + user_id.
    This provides isolation: compromising one user's token doesn't compromise others.
    """
    base_key = MASTER_KEY.encode()
    # Derive a 32-byte key using SHA256
    derived = hashlib.sha256(base_key + user_id.encode()).digest()
    # Fernet requires base64-encoded 32-byte key
    fernet_key = base64.urlsafe_b64encode(derived)
    return Fernet(fernet_key)

def encrypt_token(token: str, user_id: str) -> str:
    """Шифрует строку токена с использованием уникального ключа пользователя."""
    fernet = _get_user_key(user_id)
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str, user_id: str) -> str:
    """Расшифровывает зашифрованную строку токена с использованием ключа пользователя."""
    fernet = _get_user_key(user_id)
    return fernet.decrypt(encrypted_token.encode()).decode()