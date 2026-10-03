from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass(frozen=True)
class MailDeliveryReceipt:
    provider_message_id: str | None = None


@dataclass(frozen=True)
class MailProviderCapabilities:
    """Описывает возможности транспорта без привязки бизнес-логики к его названию."""

    transport_kind: str
    transactional: bool = True
    marketing: bool = False
    custom_headers: bool = False
    rfc_headers: bool = False
    one_click_unsubscribe: bool = False
    reply_to: bool = False
    preview_title: bool = False
    idempotency_key: bool = False
    provider_managed_tls: bool = False
    provider_managed_ptr: bool = False
    outbound_port: int | None = None

    def as_payload(self) -> dict:
        return asdict(self)


class MailProviderError(RuntimeError):
    """Безопасная ошибка транспортного адаптера, пригодная для общей обработки."""

    def __init__(
        self,
        code: str,
        *,
        provider_code: str,
        retryable: bool,
        user_message: str,
        provider_error_code: str | None = None,
    ) -> None:
        super().__init__(code)
        self.code = str(code or "mail_provider_error")[:96]
        self.provider_code = str(provider_code or "unknown")[:64]
        self.retryable = bool(retryable)
        self.user_message = str(user_message or "Почтовый провайдер не принял сообщение.")[:500]
        self.provider_error_code = (
            str(provider_error_code)[:64]
            if provider_error_code
            else None
        )

    @property
    def safe_code(self) -> str:
        if not self.provider_error_code:
            return self.code
        return f"{self.code}:{self.provider_error_code}"[:96]


class MailProvider(Protocol):
    """Контракт транспортного адаптера для устойчивого сервиса почтовой доставки."""

    code: str
    display_name: str
    capabilities: MailProviderCapabilities
    configuration_kind: str
    default_port: int
    default_api_base_url: str | None
    key_id_numeric: bool

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
            raise ValueError("Код почтового провайдера обязателен")
        self._providers[code] = provider

    def get(self, code: str) -> MailProvider:
        normalized = str(code or "").strip().lower()
        try:
            return self._providers[normalized]
        except KeyError as exc:
            raise RuntimeError(
                f"Почтовый провайдер не зарегистрирован: {normalized or 'пустое значение'}"
            ) from exc

    @property
    def codes(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))
