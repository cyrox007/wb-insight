import json

import httpx
import pytest

from integrations.sber.client import (
    SberAcquiringClient,
    SberAcquiringError,
    SberOrderStatus,
)
from models.payments_model import PaymentProvider
from services.payment_service import normalize_sber_status, safe_sber_provider_data


@pytest.mark.asyncio
async def test_register_order_uses_server_credentials_and_kopecks():
    async def handler(request: httpx.Request):
        assert request.url.path.endswith("/register.do")
        payload = json.loads(request.content)
        assert payload["userName"] == "merchant-login"
        assert payload["password"] == "merchant-password"
        assert payload["orderNumber"] == "WBI-123"
        assert payload["amount"] == 199900
        assert payload["currency"] == "643"
        assert payload["returnUrl"] == "https://app.example/billing/success?payment_id=123"
        assert payload["failUrl"] == "https://app.example/billing/success?payment_id=123&result=fail"
        return httpx.Response(
            200,
            json={
                "errorCode": "0",
                "errorMessage": "OK",
                "orderId": "bank-order-id",
                "formUrl": "https://ecomtest.sberbank.ru/pp/pay_ru?orderId=bank-order-id",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = SberAcquiringClient(
            base_url="https://gateway.example/api/v1",
            username="merchant-login",
            password="merchant-password",
            http_client=http_client,
        )
        registered = await client.register_order(
            order_number="WBI-123",
            amount_kopecks=199900,
            currency="643",
            return_url="https://app.example/billing/success?payment_id=123",
            fail_url="https://app.example/billing/success?payment_id=123&result=fail",
            description="WB Insight: тариф Pro",
        )

    assert registered.order_id == "bank-order-id"
    assert registered.form_url.startswith("https://ecomtest.sberbank.ru/")


@pytest.mark.asyncio
async def test_extended_status_requires_deposited_state_for_paid():
    async def handler(request: httpx.Request):
        assert request.url.path.endswith("/getOrderStatusExtended.do")
        payload = json.loads(request.content)
        assert payload["orderId"] == "bank-order-id"
        assert payload["userName"] == "merchant-login"
        return httpx.Response(
            200,
            json={
                "errorCode": "0",
                "orderId": "bank-order-id",
                "orderStatus": 2,
                "paymentState": "DEPOSITED",
                "amount": 199900,
                "currency": "643",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = SberAcquiringClient(
            base_url="https://gateway.example/api/v1",
            username="merchant-login",
            password="merchant-password",
            http_client=http_client,
        )
        bank_status = await client.get_order_status(order_id="bank-order-id")

    assert bank_status.order_status == 2
    assert bank_status.payment_state == "DEPOSITED"
    assert bank_status.is_paid is True
    assert normalize_sber_status(bank_status) == "2:DEPOSITED"


def test_order_status_two_without_deposited_is_not_paid():
    status = SberOrderStatus(
        order_status=2,
        payment_state="CREATED",
        raw={"orderStatus": 2, "paymentState": "CREATED"},
    )
    assert status.is_paid is False


@pytest.mark.asyncio
async def test_gateway_operation_error_is_user_safe():
    async def handler(_request: httpx.Request):
        return httpx.Response(
            200,
            json={
                "errorCode": "5",
                "errorMessage": "merchant internal diagnostic with sensitive detail",
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = SberAcquiringClient(
            base_url="https://gateway.example/api/v1",
            username="merchant-login",
            password="merchant-password",
            http_client=http_client,
        )
        with pytest.raises(SberAcquiringError) as exc_info:
            await client.register_order(
                order_number="WBI-123",
                amount_kopecks=100,
                return_url="https://app.example/ok",
                fail_url="https://app.example/fail",
                description="test",
            )

    assert exc_info.value.code == "SBER_OPERATION_REJECTED"
    assert "sensitive detail" not in str(exc_info.value)
    assert "merchant-password" not in str(exc_info.value)


@pytest.mark.asyncio
async def test_transport_error_is_retryable_and_safe():
    async def handler(request: httpx.Request):
        raise httpx.ConnectError("credentials=do-not-leak", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = SberAcquiringClient(
            base_url="https://gateway.example/api/v1",
            username="merchant-login",
            password="merchant-password",
            http_client=http_client,
        )
        with pytest.raises(SberAcquiringError) as exc_info:
            await client.get_order_status(order_id="bank-order-id")

    assert exc_info.value.code == "SBER_GATEWAY_UNAVAILABLE"
    assert exc_info.value.retryable is True
    assert "do-not-leak" not in str(exc_info.value)


def test_provider_enum_contains_sber():
    assert PaymentProvider.SBER.value == "sber"


def test_provider_data_filter_drops_unknown_sensitive_fields():
    filtered = safe_sber_provider_data(
        {
            "orderStatus": 2,
            "paymentState": "DEPOSITED",
            "pan": "411111******1111",
            "clientEmail": "seller@example.com",
        }
    )
    assert filtered == {"orderStatus": 2, "paymentState": "DEPOSITED"}
