import re
from html import escape

import httpx

from integrations.mail.provider import (
    MailDeliveryReceipt,
    MailProviderCapabilities,
    MailProviderError,
)


_PROVIDER_ERROR_CODE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_HEADER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,62}$")
_RESERVED_HEADERS = {
    "authorization",
    "content-type",
    "from",
    "to",
    "subject",
}


def _safe_provider_error_code(response: httpx.Response) -> str | None:
    """Извлекает только ограниченный машинный код ошибки Resend."""
    try:
        payload = response.json()
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None

    candidate = payload.get("name") or payload.get("code")
    value = str(candidate or "").strip()
    if not value or not _PROVIDER_ERROR_CODE_RE.fullmatch(value):
        return None
    return value


def _error_message(code: str) -> str:
    messages = {
        "resend_not_configured": "Настройки Resend неполные. Проверьте API-токен и адрес отправителя.",
        "resend_http_400": "Resend отклонил параметры письма. Проверьте адрес отправителя и настройки домена.",
        "resend_http_401": "Resend отклонил API-токен. Проверьте или перевыпустите ключ.",
        "resend_http_403": "Resend запретил отправку. Проверьте права API-ключа и подтверждение домена.",
        "resend_http_404": "Resend не нашёл требуемый ресурс. Проверьте настройки почтового провайдера.",
        "resend_http_422": "Resend не принял содержимое письма. Проверьте отправителя, получателя и обязательные поля.",
        "resend_http_429": "Resend временно ограничил частоту запросов. Отправка будет повторена позже.",
        "resend_timeout": "Resend не ответил вовремя. Отправка будет повторена позже.",
        "resend_network_error": "Не удалось подключиться к Resend по HTTPS.",
    }
    return messages.get(code, "Resend не принял письмо. Проверьте настройки транспорта.")


def _address_with_name(email: str, name: str | None) -> str:
    """Формирует JSON-адрес API без MIME-кодирования Unicode-имени."""
    clean_email = str(email or "").strip()
    clean_name = str(name or "").strip()
    if "\r" in clean_email or "\n" in clean_email:
        raise ValueError("Недопустимый email почтового сообщения")
    if not clean_name:
        return clean_email
    if "\r" in clean_name or "\n" in clean_name:
        raise ValueError("Недопустимое имя участника почтового сообщения")
    # API принимает форму `Имя <email>`. Угловые скобки в отображаемом имени
    # убираются, чтобы имя не могло изменить адресную часть строки.
    clean_name = clean_name.replace("<", "").replace(">", "").strip()
    return f"{clean_name[:255]} <{clean_email}>" if clean_name else clean_email


class ResendAPIError(MailProviderError):
    """Безопасная ошибка HTTPS-адаптера Resend."""

    def __init__(
        self,
        code: str,
        *,
        retryable: bool,
        provider_error_code: str | None = None,
    ) -> None:
        safe_provider_code = (
            provider_error_code
            if provider_error_code and _PROVIDER_ERROR_CODE_RE.fullmatch(provider_error_code)
            else None
        )
        super().__init__(
            code,
            provider_code="resend",
            retryable=retryable,
            user_message=_error_message(code),
            provider_error_code=safe_provider_code,
        )


class ResendMailProvider:
    code = "resend"
    display_name = "Resend API"
    configuration_kind = "https_api_key"
    default_port = 443
    default_api_base_url = "https://api.resend.com"
    requires_key_id = False
    key_id_numeric = False
    environment_api_base_url_attr = "RESEND_API_BASE_URL"
    environment_key_id_attr = None
    environment_api_token_attr = "RESEND_API_TOKEN"
    environment_timeout_attr = "RESEND_TIMEOUT_SECONDS"
    capabilities = MailProviderCapabilities(
        transport_kind="https_api",
        transactional=True,
        marketing=True,
        custom_headers=True,
        rfc_headers=True,
        one_click_unsubscribe=True,
        reply_to=True,
        preview_title=True,
        idempotency_key=True,
        provider_managed_tls=True,
        provider_managed_ptr=True,
        outbound_port=443,
    )

    def __init__(self, config) -> None:
        self._config = config

    @staticmethod
    def _safe_headers(headers: dict[str, str] | None) -> dict[str, str]:
        result: dict[str, str] = {}
        for raw_name, raw_value in (headers or {}).items():
            name = str(raw_name or "").strip()
            value = str(raw_value or "").strip()
            if not name or not value:
                continue
            if name.lower() in _RESERVED_HEADERS:
                continue
            if not _HEADER_NAME_RE.fullmatch(name):
                continue
            if "\r" in value or "\n" in value:
                raise ValueError("Недопустимый почтовый заголовок")
            result[name] = value[:998]
        return result

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
        base_url = str(self._config.API_BASE_URL or self.default_api_base_url).rstrip("/")
        token = str(self._config.API_TOKEN or "").strip()
        timeout = float(self._config.API_TIMEOUT_SECONDS or 10.0)
        if not base_url or not token:
            raise ResendAPIError("resend_not_configured", retryable=False)

        html_payload = html_body
        if html_payload and preview_title:
            preheader = (
                '<div style="display:none!important;visibility:hidden;opacity:0;'
                'color:transparent;height:0;width:0;overflow:hidden;mso-hide:all;">'
                + escape(str(preview_title)[:255])
                + "</div>"
            )
            html_payload = preheader + html_payload

        payload: dict[str, object] = {
            "from": _address_with_name(sender, sender_name),
            "to": [_address_with_name(recipient, recipient_name)],
            "subject": subject[:255],
        }
        if body:
            payload["text"] = body
        if html_payload:
            payload["html"] = html_payload
        if reply_to:
            payload["reply_to"] = reply_to

        safe_headers = self._safe_headers(headers)
        if safe_headers:
            payload["headers"] = safe_headers

        request_headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        if idempotency_key:
            request_headers["Idempotency-Key"] = str(idempotency_key)[:256]

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{base_url}/emails",
                    headers=request_headers,
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise ResendAPIError("resend_timeout", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise ResendAPIError("resend_network_error", retryable=True) from exc

        if 200 <= response.status_code < 300:
            provider_id = None
            try:
                data = response.json()
            except (TypeError, ValueError):
                data = None
            if isinstance(data, dict):
                value = str(data.get("id") or "").strip()
                provider_id = value or None
            return MailDeliveryReceipt(provider_message_id=provider_id)

        code = f"resend_http_{response.status_code}"
        retryable = response.status_code == 429 or response.status_code >= 500
        raise ResendAPIError(
            code,
            retryable=retryable,
            provider_error_code=_safe_provider_error_code(response),
        )
