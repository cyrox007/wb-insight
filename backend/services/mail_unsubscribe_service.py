import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from urllib.parse import quote

from core.lifecycle_config import lifecycle_config


@dataclass(frozen=True)
class UnsubscribeIdentity:
    user_id: str | None
    email: str
    list_id: str


def _key() -> bytes:
    value = lifecycle_config.MAIL_UNSUBSCRIBE_HMAC_KEY.encode("utf-8")
    if len(value) < 32:
        raise RuntimeError("mail_unsubscribe_hmac_key_not_configured")
    return value


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


def create_unsubscribe_token(
    *,
    email: str,
    user_id=None,
    list_id: str = "marketing",
) -> str:
    normalized_email = str(email or "").strip().lower()
    if not normalized_email or "@" not in normalized_email:
        raise ValueError("unsubscribe_email_required")

    payload = {
        "v": 1,
        "uid": str(user_id) if user_id else None,
        "email": normalized_email,
        "list": str(list_id or "marketing").strip().lower() or "marketing",
    }
    encoded = _b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signature = _b64encode(
        hmac.new(_key(), encoded.encode("ascii"), hashlib.sha256).digest()
    )
    return f"{encoded}.{signature}"


def parse_unsubscribe_token(token: str) -> UnsubscribeIdentity:
    try:
        encoded, signature = str(token or "").split(".", 1)
        expected = _b64encode(
            hmac.new(_key(), encoded.encode("ascii"), hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            raise ValueError("unsubscribe_token_invalid")
        payload = json.loads(_b64decode(encoded).decode("utf-8"))
    except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("unsubscribe_token_invalid") from exc

    if payload.get("v") != 1:
        raise ValueError("unsubscribe_token_invalid")
    email = str(payload.get("email") or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("unsubscribe_token_invalid")
    return UnsubscribeIdentity(
        user_id=str(payload.get("uid") or "") or None,
        email=email,
        list_id=str(payload.get("list") or "marketing").strip().lower() or "marketing",
    )


def unsubscribe_url(
    *,
    email: str,
    user_id=None,
    list_id: str = "marketing",
) -> str:
    base = lifecycle_config.MAIL_UNSUBSCRIBE_BASE_URL.rstrip("/")
    if not base:
        raise RuntimeError("mail_unsubscribe_base_url_not_configured")
    token = create_unsubscribe_token(
        email=email,
        user_id=user_id,
        list_id=list_id,
    )
    return f"{base}/{quote(token, safe='')}"
