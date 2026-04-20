from cryptography.fernet import Fernet

from settings import config

key = config.ENCRYPTION_KEY
assert key is not None

fernet = Fernet(key.encode())

def encrypt_token(token: str) -> str:
    """Шифрует строку токена и возвращает base64-строку."""
    return fernet.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    """Расшифровывает зашифрованную строку токена."""
    return fernet.decrypt(encrypted_token.encode()).decode()