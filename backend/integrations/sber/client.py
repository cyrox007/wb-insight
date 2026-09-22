from dataclasses import dataclass
from typing import Any

import httpx


class SberAcquiringError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "SBER_ACQUIRING_ERROR",
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class SberRegisteredOrder:
    order_id: str
    form_url: str
    raw: dict[str, Any]


@dataclass(frozen=True)
class SberOrderStatus:
    order_status: int | None
    payment_state: str | None
    raw: dict[str, Any]

    @property
    def is_paid(self) -> bool:
        # Для одностадийного эквайринга подтверждённый шлюзом статус зачисления
        # является достоверным признаком оплаты. Требуем оба документированных
        # признака, чтобы не активировать подписку из промежуточного состояния.
        return self.order_status == 2 and self.payment_state == "DEPOSITED"


class SberAcquiringClient:
    def __init__(
        self,
        *,
        base_url: str,
        username: str,
        password: str,
        timeout_seconds: float = 10.0,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(timeout=timeout_seconds)

    async def __aenter__(self) -> "SberAcquiringClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = {
            "userName": self._username,
            "password": self._password,
            **payload,
        }
        try:
            response = await self._client.post(
                f"{self._base_url}/{endpoint}",
                json=body,
                headers={"Content-Type": "application/json"},
            )
        except httpx.TransportError as exc:
            raise SberAcquiringError(
                "Платёжный шлюз Сбера временно недоступен",
                code="SBER_GATEWAY_UNAVAILABLE",
                retryable=True,
            ) from exc

        if response.status_code >= 500:
            raise SberAcquiringError(
                "Платёжный шлюз Сбера временно недоступен",
                code="SBER_GATEWAY_UNAVAILABLE",
                retryable=True,
            )
        if not response.is_success:
            raise SberAcquiringError(
                "Платёжный шлюз Сбера отклонил запрос",
                code="SBER_GATEWAY_REJECTED",
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise SberAcquiringError(
                "Платёжный шлюз Сбера вернул некорректный ответ",
                code="SBER_GATEWAY_INVALID_RESPONSE",
                retryable=True,
            ) from exc
        if not isinstance(data, dict):
            raise SberAcquiringError(
                "Платёжный шлюз Сбера вернул некорректный ответ",
                code="SBER_GATEWAY_INVALID_RESPONSE",
                retryable=True,
            )
        return data

    @staticmethod
    def _raise_gateway_error(data: dict[str, Any]) -> None:
        error_code = data.get("errorCode")
        if error_code in (None, 0, "0"):
            return
        raise SberAcquiringError(
            "Платёжный шлюз Сбера не смог обработать операцию",
            code="SBER_OPERATION_REJECTED",
        )

    async def register_order(
        self,
        *,
        order_number: str,
        amount_kopecks: int,
        return_url: str,
        fail_url: str,
        description: str,
        currency: str = "643",
    ) -> SberRegisteredOrder:
        if amount_kopecks <= 0:
            raise ValueError("Сумма платежа в копейках должна быть больше нуля")

        data = await self._post(
            "register.do",
            {
                "orderNumber": order_number,
                "amount": amount_kopecks,
                "currency": currency,
                "returnUrl": return_url,
                "failUrl": fail_url,
                "description": description,
                "language": "ru",
            },
        )
        self._raise_gateway_error(data)

        order_id = str(data.get("orderId") or "").strip()
        form_url = str(data.get("formUrl") or "").strip()
        if not order_id or not form_url:
            raise SberAcquiringError(
                "Платёжный шлюз Сбера не вернул данные платёжной формы",
                code="SBER_GATEWAY_INVALID_RESPONSE",
                retryable=True,
            )
        return SberRegisteredOrder(order_id=order_id, form_url=form_url, raw=data)

    async def get_order_status(self, *, order_id: str) -> SberOrderStatus:
        data = await self._post(
            "getOrderStatusExtended.do",
            {"orderId": order_id},
        )
        self._raise_gateway_error(data)

        raw_order_status = data.get("orderStatus")
        try:
            order_status = int(raw_order_status) if raw_order_status is not None else None
        except (TypeError, ValueError):
            order_status = None

        payment_state = data.get("paymentState")
        if payment_state is not None:
            payment_state = str(payment_state).strip().upper() or None

        return SberOrderStatus(
            order_status=order_status,
            payment_state=payment_state,
            raw=data,
        )
