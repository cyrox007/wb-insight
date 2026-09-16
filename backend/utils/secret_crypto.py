import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from settings import config


def _fernet(context: str) -> Fernet:
    master_key = config.ENCRYPTION_KEY
    if not master_key:
        raise RuntimeError("API_TOKEN_ENCRYPTION_KEY is required to store payment secrets")
    derived = hashlib.sha256(
        master_key.encode("utf-8") + b"\0" + context.encode("utf-8")
    ).digest()
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_secret_payload(payload: dict[str, Any], *, context: str) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return _fernet(context).encrypt(raw).decode("ascii")


def decrypt_secret_payload(value: str | None, *, context: str) -> dict[str, Any]:
    if not value:
        return {}
    try:
        raw = _fernet(context).decrypt(value.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
    except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError("Payment provider secrets cannot be decrypted") from exc
    if not isinstance(data, dict):
        raise RuntimeError("Payment provider secrets have invalid format")
    return data
