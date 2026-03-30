"""Модуль шифрования и дешифрования токенов.

Использует алгоритм Fernet для симметричного шифрования.
"""

from cryptography.fernet import Fernet

from settings import config


# Инициализация шифровальщика
fernet = Fernet(config.ENCRYPTION_KEY.encode())


def encrypt_token(token: str) -> str:
    """Шифрует строку токена и возвращает base64-строку.
    
    Args:
        token: Исходная строка токена.
        
    Returns:
        Зашифрованная строка в формате base64.
    """
    return fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Расшифровывает зашифрованную строку токена.
    
    Args:
        encrypted_token: Зашифрованная строка токена.
        
    Returns:
        Расшифрованная исходная строка токена.
    """
    return fernet.decrypt(encrypted_token.encode()).decode()