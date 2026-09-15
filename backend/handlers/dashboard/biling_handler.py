from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from integrations.sber.client import SberAcquiringClient, SberAcquiringError
from models.payments_model import PaymentProvider, PaymentStatus
from models.tariffs_model import TariffPlan
from services.payment_service import (
    apply_sber_status,
    create_or_get_payment,
    create_payment,
    fake_pay,
    get_payment,
    get_payment_by_external_id,
    record_payment_event,
    safe_sber_provider_data,
)
from services.subscription_service import (
    create_subscription,
    deactivate_active_subscriptions,
    get_subscription_by_payment_id,
)
from settings import config
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/billing", tags=["Billing"])


def _append_query(url: str, **params: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qs(parts.query, keep_blank_values=True))
    flat = {key: values[-1] if isinstance(values, list) else values for key, values in query.items()}
    flat.update(params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(flat), parts.fragment))


def _amount_to_kopecks(amount: Decimal) -> int:
    return int((amount * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _sber_client() -> SberAcquiringClient:
    return SberAcquiringClient(
        base_url=config.SBER_API_BASE_URL,
        username=config.SBER_USERNAME or "",
        password=config.SBER_PASSWORD or "",
        timeout_seconds=config.SBER_HTTP_TIMEOUT_SECONDS,
    )


def _payment_payload(payment, *, confirmation_url: str | None = None) -> dict:
    payload = {
        "payment_id": str(payment.id),
        "payment_status": payment.status.value,
        "provider": payment.provider.value,
        "provider_status": payment.provider_status,
        "amount": str(payment.amount),
        "currency": payment.currency,
    }
    if confirmation_url:
        payload["confirmation_url"] = confirmation_url
    return payload


async def _get_tariff(session: AsyncSession, tariff_code: str) -> TariffPlan | None:
    result = await session.execute(
        select(TariffPlan).where(
            TariffPlan.code == tariff_code,
            TariffPlan.is_active.is_(True),
            TariffPlan.is_public.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def _confirm_sber_payment(
    session: AsyncSession,
    payment,
    *,
    event_type: str,
):
    if payment.provider != PaymentProvider.SBER:
        raise ValueError("Платёж создан другим провайдером")
    if not payment.external_payment_id:
        raise ValueError("Платёж ещё не зарегистрирован в Сбере")

    async with _sber_client() as client:
        bank_status = await client.get_order_status(order_id=payment.external_payment_id)

    return await apply_sber_status(
        session,
        payment_id=payment.id,
        status=bank_status,
        event_type=event_type,
    )


@router.post("/create-payment", dependencies=[Depends(auth_middle)])
async def create_payment_handler(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    if not config.SBER_ACQUIRING_ENABLED and not config.ALLOW_FAKE_BILLING:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return response_error(
            code="BILLING_NOT_CONFIGURED",
            message="Платёжный провайдер пока не подключён",
        )

    body = await request.json()
    tariff_code = str(body.get("tariff_code") or "").strip()
    if not tariff_code:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="VALIDATION_ERROR", message="Тариф обязателен")

    tariff = await _get_tariff(db_session, tariff_code)
    if tariff is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="TARIFF_NOT_FOUND", message="Тариф не найден")

    amount = Decimal(tariff.price_rub)
    if amount <= 0:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="TARIFF_NOT_PAYABLE",
            message="Бесплатный тариф не требует платёжной операции",
        )

    user_id = UUID(str(request.state.user["sub"]))

    if config.SBER_ACQUIRING_ENABLED:
        idempotency_key = str(request.headers.get("Idempotency-Key") or "").strip()
        if not 8 <= len(idempotency_key) <= 128:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return response_error(
                code="IDEMPOTENCY_KEY_REQUIRED",
                message="Для создания платежа требуется Idempotency-Key длиной 8–128 символов",
            )

        try:
            payment, created = await create_or_get_payment(
                db_session,
                user_id=user_id,
                tariff_id=tariff.id,
                amount=amount,
                provider=PaymentProvider.SBER,
                idempotency_key=idempotency_key,
            )
        except ValueError as exc:
            response.status_code = status.HTTP_409_CONFLICT
            return response_error(code="IDEMPOTENCY_CONFLICT", message=str(exc))

        existing_url = (payment.provider_data or {}).get("form_url")
        if payment.external_payment_id and existing_url:
            return response_success(**_payment_payload(payment, confirmation_url=existing_url))
        if payment.status != PaymentStatus.PENDING:
            response.status_code = status.HTTP_409_CONFLICT
            return response_error(
                code="PAYMENT_NOT_PENDING",
                message="Эта платёжная попытка уже завершена",
                payment_id=str(payment.id),
                payment_status=payment.status.value,
            )

        return_url = _append_query(
            config.SBER_RETURN_URL or "",
            payment_id=str(payment.id),
            result="return",
        )
        fail_url = _append_query(
            config.SBER_FAIL_URL or "",
            payment_id=str(payment.id),
            result="fail",
        )
        order_number = f"WBI-{payment.id.hex}"

        try:
            async with _sber_client() as client:
                registered = await client.register_order(
                    order_number=order_number,
                    amount_kopecks=_amount_to_kopecks(amount),
                    currency=config.SBER_CURRENCY_CODE,
                    return_url=return_url,
                    fail_url=fail_url,
                    description=f"WB Insight: тариф {tariff.name}",
                )
        except SberAcquiringError as exc:
            await record_payment_event(
                db_session,
                payment_id=payment.id,
                event_type="registration_error",
                provider_status=exc.code,
                provider_data={"retryable": exc.retryable},
            )
            response.status_code = (
                status.HTTP_503_SERVICE_UNAVAILABLE
                if exc.retryable
                else status.HTTP_502_BAD_GATEWAY
            )
            return response_error(code=exc.code, message=str(exc))

        payment.external_payment_id = registered.order_id
        payment.provider_status = "REGISTERED"
        payment.provider_data = {
            "order_number": order_number,
            "form_url": registered.form_url,
            "registration": safe_sber_provider_data(registered.raw),
        }
        await record_payment_event(
            db_session,
            payment_id=payment.id,
            event_type="registered" if created else "registered_after_retry",
            provider_status="REGISTERED",
            provider_data={
                "order_id": registered.order_id,
                "order_number": order_number,
            },
        )
        await db_session.flush()
        return response_success(
            **_payment_payload(payment, confirmation_url=registered.form_url)
        )

    payment = await create_payment(
        db_session,
        user_id=user_id,
        tariff_id=tariff.id,
        amount=amount,
        provider=PaymentProvider.FAKE,
    )
    return response_success(**_payment_payload(payment))


@router.get("/payments/{payment_id}", dependencies=[Depends(auth_middle)])
async def get_payment_handler(
    payment_id: UUID,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    payment = await get_payment(db_session, payment_id)
    user_id = UUID(str(request.state.user["sub"]))
    if payment is None or payment.user_id != user_id:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="PAYMENT_NOT_FOUND", message="Платёж не найден")
    return response_success(**_payment_payload(payment))


@router.post("/payments/{payment_id}/confirm", dependencies=[Depends(auth_middle)])
async def confirm_payment_handler(
    payment_id: UUID,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    payment = await get_payment(db_session, payment_id)
    user_id = UUID(str(request.state.user["sub"]))
    if payment is None or payment.user_id != user_id:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="PAYMENT_NOT_FOUND", message="Платёж не найден")

    if payment.provider == PaymentProvider.FAKE:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="PAYMENT_PROVIDER_MISMATCH",
            message="Fake-платёж подтверждается только development endpoint",
        )

    try:
        payment, subscription = await _confirm_sber_payment(
            db_session,
            payment,
            event_type="user_confirmation",
        )
    except SberAcquiringError as exc:
        response.status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
            if exc.retryable
            else status.HTTP_502_BAD_GATEWAY
        )
        return response_error(code=exc.code, message=str(exc))
    except ValueError as exc:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(code="PAYMENT_CONFIRMATION_ERROR", message=str(exc))

    return response_success(
        **_payment_payload(payment),
        subscription_id=str(subscription.id) if subscription else None,
    )


async def _callback_params(request: Request) -> dict[str, str]:
    params = {key: value for key, value in request.query_params.items()}
    if params:
        return params
    content_type = request.headers.get("content-type", "")
    body = await request.body()
    if body and "application/x-www-form-urlencoded" in content_type:
        parsed = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
        return {key: values[-1] for key, values in parsed.items() if values}
    return {}


@router.api_route("/sber/callback", methods=["GET", "POST"])
async def sber_callback_handler(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    """Treat the callback only as a trigger; bank status is re-queried server-side."""
    if not config.SBER_ACQUIRING_ENABLED:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return response_error(code="BILLING_NOT_CONFIGURED", message="Sber acquiring отключён")

    params = await _callback_params(request)
    external_id = str(params.get("mdOrder") or params.get("orderId") or "").strip()
    if not external_id:
        # A callback without an order identifier cannot mutate payment state.
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="CALLBACK_INVALID", message="Не указан идентификатор заказа")

    payment = await get_payment_by_external_id(
        db_session,
        provider=PaymentProvider.SBER,
        external_payment_id=external_id,
    )
    if payment is None:
        # Do not leak whether a provider-side order exists in our database.
        return response_success(accepted=True)

    callback_data = {
        key: params[key]
        for key in ("mdOrder", "orderId", "orderNumber", "operation", "status")
        if key in params
    }
    await record_payment_event(
        db_session,
        payment_id=payment.id,
        event_type="callback_received",
        provider_status=str(params.get("status") or "") or None,
        provider_data=callback_data,
    )

    try:
        await _confirm_sber_payment(
            db_session,
            payment,
            event_type="callback_verified",
        )
    except SberAcquiringError as exc:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return response_error(code=exc.code, message="Статус платежа пока не подтверждён")
    except ValueError:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(code="PAYMENT_CONFIRMATION_ERROR", message="Не удалось подтвердить платёж")

    return response_success(accepted=True)


@router.post("/pay-now", dependencies=[Depends(auth_middle)])
async def pay_now(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    if not config.ALLOW_FAKE_BILLING:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return response_error(
            code="BILLING_NOT_CONFIGURED",
            message="Fake-оплата отключена",
        )

    body = await request.json()
    payment_id_raw = body.get("payment_id")
    try:
        payment_id = UUID(str(payment_id_raw))
    except (TypeError, ValueError):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="VALIDATION_ERROR", message="Некорректный payment_id")

    payment = await get_payment(db_session, payment_id)
    user_id = UUID(str(request.state.user["sub"]))
    if payment is None or payment.user_id != user_id:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="PAYMENT_NOT_FOUND", message="Платёж не найден")

    try:
        payment = await fake_pay(db_session, payment_id)
        subscription = await get_subscription_by_payment_id(db_session, payment.id)
        if subscription is None:
            await deactivate_active_subscriptions(db_session, payment.user_id)
            subscription = await create_subscription(
                db_session,
                payment.user_id,
                payment.tariff_id,
                payment_id=payment.id,
            )
    except ValueError as exc:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(code="PAYMENT_STATE_ERROR", message=str(exc))

    return response_success(
        **_payment_payload(payment),
        subscription_id=str(subscription.id),
    )
