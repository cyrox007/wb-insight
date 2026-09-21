#!/usr/bin/env python3
"""Provider-neutral IMAP hook for WB Insight release mail acceptance.

The script implements the SMOKE_MAIL_TOKEN_COMMAND contract used by
ops/release_smoke.py. It receives KIND and EMAIL as the final positional
arguments, reads IMAP credentials only from environment, polls a mailbox, and
prints exactly one verification/reset URL containing #token=... to stdout.

It never prints credentials or message bodies. The release runner captures
stderr as well, so diagnostics are intentionally short and secret-free.
"""

from __future__ import annotations

import argparse
import email
from email import policy
from email.message import EmailMessage, Message
from html import unescape
import imaplib
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import getaddresses, parsedate_to_datetime
from urllib.parse import urlparse


KINDS = {
    "email_verification": {
        "subjects": {
            "Подтвердите email в WB Insight",
            "Подтвердите новый email в WB Insight",
        },
        "path_hint": "/verify-email",
    },
    "password_reset": {
        "subjects": {"Восстановление доступа к WB Insight"},
        "path_hint": "/reset-password",
    },
}

TOKEN_URL_RE = re.compile(
    r"https?://[^\s<>\"']+?#token=[A-Za-z0-9._~!$&'()*+,;=:@/?%+-]+",
    re.IGNORECASE,
)

RECIPIENT_HEADERS = (
    "To",
    "Delivered-To",
    "X-Original-To",
    "Envelope-To",
    "X-Envelope-To",
)


class HookError(RuntimeError):
    pass


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise HookError(f"{name} must be an integer") from exc
    if value < minimum or value > maximum:
        raise HookError(f"{name} is outside the accepted range")
    return value


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _message_text_parts(message: Message) -> list[str]:
    parts: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() not in {"text/plain", "text/html"}:
                continue
            try:
                payload = part.get_content()
            except (LookupError, UnicodeError):
                continue
            if isinstance(payload, str):
                parts.append(unescape(payload))
    else:
        try:
            payload = message.get_content()
        except (LookupError, UnicodeError):
            payload = ""
        if isinstance(payload, str):
            parts.append(unescape(payload))
    return parts


def _recipient_matches(message: Message, target_email: str) -> bool:
    target = _normalize_email(target_email)
    candidates: list[str] = []
    for header in RECIPIENT_HEADERS:
        candidates.extend(address for _, address in getaddresses(message.get_all(header, [])))
    return any(_normalize_email(candidate) == target for candidate in candidates if candidate)


def _message_is_recent(message: Message, *, not_before: datetime) -> bool:
    raw_date = message.get("Date")
    if not raw_date:
        # Some forwarding/catch-all systems omit Date. Recipient + subject still
        # provide a strong match, and the caller scans only a bounded recent tail.
        return True
    try:
        parsed = parsedate_to_datetime(raw_date)
    except (TypeError, ValueError, OverflowError):
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc) >= not_before


def _extract_matching_url(
    raw_message: bytes,
    *,
    kind: str,
    target_email: str,
    not_before: datetime,
) -> str | None:
    message = email.message_from_bytes(raw_message, policy=policy.default)
    spec = KINDS[kind]
    subject = str(message.get("Subject") or "").strip()
    if subject not in spec["subjects"]:
        return None
    if not _recipient_matches(message, target_email):
        return None
    if not _message_is_recent(message, not_before=not_before):
        return None

    for text in _message_text_parts(message):
        for match in TOKEN_URL_RE.finditer(text):
            candidate = unescape(match.group(0)).rstrip(").,;")
            parsed = urlparse(candidate)
            if spec["path_hint"] not in parsed.path:
                continue
            if not parsed.fragment.startswith("token="):
                continue
            token = parsed.fragment.removeprefix("token=").strip()
            if 16 <= len(token) <= 1024 and not any(char.isspace() for char in token):
                return candidate
    return None


def _uids_from_search(connection: imaplib.IMAP4_SSL) -> list[bytes]:
    status, data = connection.uid("search", None, "ALL")
    if status != "OK" or not data:
        raise HookError("IMAP search failed")
    return [uid for uid in data[0].split() if uid]


def _fetch_message(connection: imaplib.IMAP4_SSL, uid: bytes) -> bytes | None:
    status, data = connection.uid("fetch", uid, "(BODY.PEEK[])")
    if status != "OK" or not data:
        return None
    for item in data:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
            return item[1]
    return None


def _poll(kind: str, target_email: str) -> str:
    host = str(os.getenv("SMOKE_IMAP_HOST") or "").strip()
    username = str(os.getenv("SMOKE_IMAP_USERNAME") or "").strip()
    password = str(os.getenv("SMOKE_IMAP_PASSWORD") or "")
    mailbox = str(os.getenv("SMOKE_IMAP_MAILBOX") or "INBOX").strip() or "INBOX"
    port = _env_int("SMOKE_IMAP_PORT", 993, minimum=1, maximum=65535)
    poll_seconds = _env_int("SMOKE_IMAP_POLL_SECONDS", 5, minimum=1, maximum=60)
    max_messages = _env_int("SMOKE_IMAP_MAX_MESSAGES", 80, minimum=1, maximum=500)
    lookback_minutes = _env_int("SMOKE_IMAP_LOOKBACK_MINUTES", 10, minimum=1, maximum=1440)

    if not host or not username or not password:
        raise HookError("SMOKE_IMAP_HOST/USERNAME/PASSWORD are required")

    not_before = datetime.now(timezone.utc) - timedelta(minutes=lookback_minutes)
    seen_uids: set[bytes] = set()

    while True:
        try:
            with imaplib.IMAP4_SSL(host, port, timeout=30) as connection:
                status, _ = connection.login(username, password)
                if status != "OK":
                    raise HookError("IMAP login failed")
                status, _ = connection.select(mailbox, readonly=True)
                if status != "OK":
                    raise HookError("IMAP mailbox selection failed")

                uids = _uids_from_search(connection)
                for uid in reversed(uids[-max_messages:]):
                    if uid in seen_uids:
                        continue
                    seen_uids.add(uid)
                    raw = _fetch_message(connection, uid)
                    if raw is None:
                        continue
                    match = _extract_matching_url(
                        raw,
                        kind=kind,
                        target_email=target_email,
                        not_before=not_before,
                    )
                    if match:
                        return match
        except (imaplib.IMAP4.error, OSError, TimeoutError) as exc:
            # Do not include server responses: providers can echo mailbox/user
            # details in authentication errors.
            raise HookError("IMAP connection or authentication failed") from exc

        time.sleep(poll_seconds)


def _self_test() -> None:
    target = "release-smoke+abc@example.com"
    verification = EmailMessage()
    verification["From"] = "WB Insight <no-reply@mail.jsinteractive.ru>"
    verification["To"] = target
    verification["Date"] = "Sun, 21 Sep 2026 15:00:00 +0000"
    verification["Subject"] = "Подтвердите email в WB Insight"
    verification.set_content(
        "https://app.example.com/verify-email#token=0123456789abcdef0123456789abcdef"
    )
    raw = verification.as_bytes()

    match = _extract_matching_url(
        raw,
        kind="email_verification",
        target_email=target,
        not_before=datetime(2026, 9, 21, 14, 55, tzinfo=timezone.utc),
    )
    assert match == "https://app.example.com/verify-email#token=0123456789abcdef0123456789abcdef"

    wrong_target = _extract_matching_url(
        raw,
        kind="email_verification",
        target_email="other@example.com",
        not_before=datetime(2026, 9, 21, 14, 55, tzinfo=timezone.utc),
    )
    assert wrong_target is None

    reset = EmailMessage()
    reset["To"] = "seller@example.com"
    reset["Subject"] = "Восстановление доступа к WB Insight"
    reset.set_content("Откройте ссылку восстановления.")
    reset.add_alternative(
        '<a href="https://app.example.com/reset-password#token=abcdefghijklmnop12345678">reset</a>',
        subtype="html",
    )
    assert _extract_matching_url(
        reset.as_bytes(),
        kind="password_reset",
        target_email="seller@example.com",
        not_before=datetime.now(timezone.utc) - timedelta(days=1),
    ) == "https://app.example.com/reset-password#token=abcdefghijklmnop12345678"
    print("[ok] IMAP mail token hook self-test")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", nargs="?")
    parser.add_argument("email", nargs="?")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        _self_test()
        return 0

    kind = str(args.kind or os.getenv("WB_SMOKE_MAIL_KIND") or "").strip()
    target_email = _normalize_email(
        str(args.email or os.getenv("WB_SMOKE_EMAIL") or "")
    )
    if kind not in KINDS:
        raise HookError("unsupported mail kind")
    if target_email.count("@") != 1 or any(char.isspace() for char in target_email):
        raise HookError("invalid target email")

    print(_poll(kind, target_email), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HookError as exc:
        print(f"[failed] {exc}", file=sys.stderr)
        raise SystemExit(1)
