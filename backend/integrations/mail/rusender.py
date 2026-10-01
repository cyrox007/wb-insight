import re

import httpx

from integrations.mail.provider import (
    MailDeliveryReceipt,
    MailProviderCapabilities,
    MailProviderError,
)


_PROVIDER_ERROR_CODE_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
_CUSTOM_HEADER_RE = re.compile(r"^X-[A-Za-z0-9][A-Za-z0-9-]{0,62}$", re.IGNORECASE)


def _safe_provider_error_code(response: httpx.Response) -> str | None:
    """Извлекает только машинный код RuSender без описания и тела ответа."""
    try:
        payload = response.json()
    except (ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None

    candidate = payload.get("code")
    if candidate is None and isinstance(payload.get("error"), dict):
        candidate = payload["error"].get("code")
    value = str(candidate or "").strip()
    if not value or not _PROVIDER_ERROR_CODE_RE.fullmatch(value):
        return None
    return value


def _rusender_error_message(code: str) -> str:
    messages = {
        "rusender_not_configured": "Настройки RuSender неполные. Проверьте Key ID, API-токен и адрес отправителя.",
        "rusender_http_401": "RuSender отклонил API-токен. Проверьте или перевыпустите токен.",
        "rusender_http_402": "RuSender сообщает, что лимит или баланс отправок исчерпан.",
        "rusender_http_403": "RuSender запретил отправку. Проверьте права ключа и разрешение на отправку писем.",
        "rusender_http_404": "RuSender не нашёл ключ отправки или домен отправителя. Проверьте Key ID и адрес From.",
        "rusender_http_422": "RuSender не может доставить письмо на указанный адрес.",
        "rusender_http_429": "RuSender временно ограничил частоту запросов. Повторите отправку позже.",
        "rusender_http_503": "RuSender временно недоступен. Повторите отправку позже.",
        "rusender_timeout": "RuSender не ответил вовремя. Повторите отправку позже.",
        "rusender_network_error": "Не удалось подключиться к RuSender по HTTPS.",
    }
    return messages.get(code, "RuSender не принял письмо. Проверьте настройки транспорта.")


class RuSenderAPIError(MailProviderError):
    """Совместимая ошибка адаптера RuSender на общем контракте провайдеров."""

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
            provider_code="rusender",
            retryable=retryable,
            user_message=_rusender_error_message(code),
            provider_error_code=safe_provider_code,
        )


class RuSenderMailProvider:
    code = "rusender"
    display_name = "RuSender API"
    capabilities = MailProviderCapabilities(
        transport_kind="https_api",
        transactional=True,
        marketing=False,
        custom_headers=True,
        rfc_headers=False,
        one_click_unsubscribe=False,
        reply_to=False,
        preview_title=True,
        idempotency_key=True,
        provider_managed_tls=True,
        provider_managed_ptr=True,
        outbound_port=443,
    )

    def __init__(self, config) -> None:
        self._config = config

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
        base_url = str(self._config.RUSENDER_API_BASE_URL or "").rstrip("/")
        key_id = str(self._config.RUSENDER_KEY_ID or "").strip()
        token = str(self._config.RUSENDER_API_TOKEN or "").strip()
        if not base_url or not key_id or not token:
            raise RuSenderAPIError("rusender_not_configured", retryable=False)

        mail_payload: dict = {
            "to": {"email": recipient},
            "from": {"email": sender},
            "subject": subject[:255],
        }
        if sender_name:
            mail_payload["from"]["name"] = sender_name
        if recipient_name:
            mail_payload["to"]["name"] = str(recipient_name)[:255]
        if preview_title:
            mail_payload["previewTitle"] = str(preview_title)[:255]

        if html_body:
            mail_payload["html"] = html_body
            if body:
                mail_payload["text"] = body
        else:
            mail_payload["text"] = body

        # API RuSender принимает пользовательские заголовки только в формате X-*.
        # Заголовки SMTP-контура здесь фильтруются, чтобы провайдер не отклонил запрос.
        safe_headers = {}
        for raw_name, raw_value in (headers or {}).items():
            name = str(raw_name or "").strip()
            value = str(raw_value or "").strip()
            if (
                not _CUSTOM_HEADER_RE.fullmatch(name)
                or not value
                or "\r" in value
                or "\n" in value
            ):
                continue
            safe_headers[name] = value[:998]
        if safe_headers:
            mail_payload["headers"] = safe_headers

        payload: dict = {"mail": mail_payload}
        if idempotency_key:
            payload["idempotencyKey"] = str(idempotency_key)[:150]

        url = f"{base_url}/api/v1/external-mails/send/{key_id}"
        try:
            async with httpx.AsyncClient(timeout=float(self._config.RUSENDER_TIMEOUT_SECONDS)) as client:
                response = await client.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise RuSenderAPIError("rusender_timeout", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise RuSenderAPIError("rusender_network_error", retryable=True) from exc

        if 200 <= response.status_code < 300:
            # После ответа 2xx провайдер уже принял запрос. Отсутствие UUID
            # не должно запускать повторную отправку и создавать дубликат.
            provider_id = None
            try:
                data = response.json()
            except (ValueError, TypeError):
                data = None
            if isinstance(data, dict):
                value = str(data.get("uuid") or "").strip()
                provider_id = value or None
            return MailDeliveryReceipt(provider_message_id=provider_id)

        error_code = f"rusender_http_{response.status_code}"
        # В журнал попадает только ограниченный машинный код. Описание провайдера
        # и сырое тело ответа не сохраняются, чтобы не протекал контекст запроса.
        provider_error_code = _safe_provider_error_code(response)
        # Ограничение частоты и серверные ошибки считаются временными.
        retryable = response.status_code == 429 or response.status_code >= 500
        raise RuSenderAPIError(
            error_code,
            retryable=retryable,
            provider_error_code=provider_error_code,
        )
