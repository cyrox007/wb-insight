from cryptography.fernet import Fernet
import pytest

from utils import token_crypto


def test_current_encryption_roundtrip_uses_user_key(monkeypatch):
    monkeypatch.setattr(
        token_crypto,
        "MASTER_KEY",
        Fernet.generate_key().decode(),
    )
    user_id = "11111111-1111-1111-1111-111111111111"
    encrypted = token_crypto.encrypt_token("секретный-токен", user_id)

    raw_token, used_legacy = token_crypto.decrypt_token_with_legacy_status(
        encrypted,
        user_id,
    )

    assert raw_token == "секретный-токен"
    assert used_legacy is False


def test_legacy_ciphertext_is_still_readable(monkeypatch):
    legacy_key = Fernet.generate_key().decode()
    monkeypatch.setattr(token_crypto, "MASTER_KEY", legacy_key)
    user_id = "22222222-2222-2222-2222-222222222222"
    legacy_fernet = Fernet(legacy_key.encode())
    encrypted = legacy_fernet.encrypt("старый-токен".encode()).decode()

    raw_token, used_legacy = token_crypto.decrypt_token_with_legacy_status(
        encrypted,
        user_id,
    )

    assert raw_token == "старый-токен"
    assert used_legacy is True


def test_unreadable_ciphertext_returns_safe_crypto_error(monkeypatch):
    monkeypatch.setattr(
        token_crypto,
        "MASTER_KEY",
        Fernet.generate_key().decode(),
    )
    with pytest.raises(token_crypto.TokenDecryptionError):
        token_crypto.decrypt_token_with_legacy_status(
            "повреждённый-ciphertext",
            "33333333-3333-3333-3333-333333333333",
        )
