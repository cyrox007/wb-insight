from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class MailDeliveryReceipt:
    provider_message_id: str | None = None


class MailProvider(Protocol):
    """Transport adapter contract used by the durable mail domain service."""

    code: str

    async def send(
        self,
        *,
        sender: str,
        recipient: str,
        subject: str,
        body: str,
        html_body: str | None = None,
        sender_name: str | None = None,
        recipient_name: str | None = None,
        preview_title: str | None = None,
        reply_to: str | None = None,
        headers: dict[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> MailDeliveryReceipt:
        ...


class MailProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, MailProvider] = {}

    def register(self, provider: MailProvider) -> None:
        code = str(provider.code).strip().lower()
        if not code:
            raise ValueError("mail_provider_code_required")
        self._providers[code] = provider

    def get(self, code: str) -> MailProvider:
        normalized = str(code or "").strip().lower()
        try:
            return self._providers[normalized]
        except KeyError as exc:
            raise RuntimeError(f"mail_provider_not_registered:{normalized or 'empty'}") from exc

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))
