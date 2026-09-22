import re

import httpx

from integrations.mail.provider import MailDeliveryReceipt


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


class RuSenderAPIError(RuntimeError):
    """Безопасная ошибка провайдера с признаком допустимости повторной попытки."""

    def __init__(
        self,
        code: str,
        *,
        retryable: bool,
        provider_error_code: str | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code[:96]
        self.retryable = retryable
        self.provider_error_code = (
            provider_error_code
            if provider_error_code and _PROVIDER_ERROR_CODE_RE.fullmatch(provider_error_code)
            else None
        )

    @property
    def safe_code(self) -> str:
        if not self.provider_error_code:
            return self.code
        return f"{self.code}:{self.provider_error_code}"[:96]


class RuSenderMailProvider:
    code = "rusender"

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

        # RuSender поддерживает пользовательские mail.headers для заголовков X-*.
        # Произвольные RFC-заголовки из SMTP-контура не передаём: шлюз может
        # отклонить такой запрос с кодом 400.
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
            # После ответа 2xx провайдер уже принял запрос. Повторная отправка
            # только из-за отсутствующего uuid в нестандартном успешном ответе
            # может создать дубликат письма. Сохраняем uuid, когда он есть, но
            # не превращаем принятую доставку в повторяемую ошибку.
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
        # RuSender возвращает машинный код ошибки в теле ответа. Для диагностики
        # сохраняем только ограниченный код; описание провайдера и сырое тело
        # ответа не сохраняем и не возвращаем, так как там может быть контекст запроса.
        provider_error_code = _safe_provider_error_code(response)
        # Ошибки 429 и 5xx считаются временными. Ошибки авторизации, отправителя,
        # домена и политики получателя требуют настройки или действий пользователя
        # и не должны запускать бесконечные повторные попытки.
        retryable = response.status_code == 429 or response.status_code >= 500
        raise RuSenderAPIError(
            error_code,
            retryable=retryable,
            provider_error_code=provider_error_code,
        )
