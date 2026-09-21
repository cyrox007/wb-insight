import httpx

from integrations.mail.provider import MailDeliveryReceipt


class RuSenderAPIError(RuntimeError):
    """Safe provider error with retry semantics for the mail worker."""

    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code[:96]
        self.retryable = retryable


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

        if html_body:
            mail_payload["html"] = html_body
            if body:
                mail_payload["text"] = body
        else:
            mail_payload["text"] = body

        # RuSender documents custom mail.headers for X-* headers. Do not forward
        # arbitrary RFC headers from the SMTP path because that can cause a 400.
        safe_headers = {
            str(name): str(value)
            for name, value in (headers or {}).items()
            if str(name).lower().startswith("x-")
        }
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

        if response.status_code == 200:
            data = response.json()
            provider_id = str(data.get("uuid") or "").strip()
            if not provider_id:
                raise RuSenderAPIError("rusender_invalid_success_response", retryable=True)
            return MailDeliveryReceipt(provider_message_id=provider_id)

        error_code = f"rusender_http_{response.status_code}"
        # 429 and 5xx are transient. Authentication, sender/domain and recipient
        # policy failures require configuration/user intervention and must not spin.
        retryable = response.status_code == 429 or response.status_code >= 500
        raise RuSenderAPIError(error_code, retryable=retryable)
