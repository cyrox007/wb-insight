from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from models.payments_model import PaymentProvider, PaymentStatus
from services.payment_service import create_payment, fake_pay, get_payment
from services.subscription_service import create_subscription, deactivate_active_subscriptions
from services.tariff_service import get_tariff_by_code
from settings import config
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/billing", tags=["Billing"])


def _billing_unavailable(response: Response) -> dict:
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return response_error(
        code="BILLING_NOT_CONFIGURED",
        message="Платёжный провайдер ещё не подключён",
    )


@router.post('/create-payment', dependencies=[Depends(auth_middle)])
async def create_payment_handler(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    # Until Sber acquiring is integrated, fake payments must be explicitly
    # enabled in a non-production environment. Never silently sell a tariff.
    if not config.ALLOW_FAKE_BILLING:
        return _billing_unavailable(response)

    data = await request.json()
    tariff_code = str(data.get('tariff_code') or '').strip().upper()
    if not tariff_code or tariff_code == "DEMO":
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="VALIDATION_ERROR",
            message="Некорректный тариф",
        )

    tariff = await get_tariff_by_code(db_session, tariff_code)
    if not tariff or not tariff.is_active or not tariff.is_public:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            code="TARIFF_NOT_FOUND",
            message="Тариф недоступен",
        )

    user_id = UUID(str(request.state.user['sub']))
    payment = await create_payment(
        db=db_session,
        user_id=user_id,
        tariff_id=UUID(str(tariff.id)),
        amount=tariff.price_rub,
        provider=PaymentProvider.FAKE,
    )

    # Important: the current subscription is intentionally left untouched.
    # It may only be replaced after a confirmed successful payment.
    return response_success(
        payment_id=str(payment.id),
        payment_amount=str(payment.amount),
        payment_status=payment.status.value,
        provider=payment.provider.value,
    )


@router.post('/pay-now', dependencies=[Depends(auth_middle)])
async def pay_now(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    if not config.ALLOW_FAKE_BILLING:
        return _billing_unavailable(response)

    data = await request.json()
    raw_payment_id = data.get('payment_id')
    if not raw_payment_id:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="VALIDATION_ERROR",
            message="Отсутствует payment_id",
        )

    try:
        payment_id = UUID(str(raw_payment_id))
        user_id = UUID(str(request.state.user['sub']))
    except (TypeError, ValueError):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="VALIDATION_ERROR",
            message="Некорректный payment_id",
        )

    payment = await get_payment(db_session, payment_id, user_id=user_id)
    if not payment:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            code="PAYMENT_NOT_FOUND",
            message="Платёж не найден",
        )

    if payment.provider != PaymentProvider.FAKE:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="INVALID_PAYMENT_PROVIDER",
            message="Платёж должен подтверждаться внешним провайдером",
        )

    if payment.status == PaymentStatus.SUCCEEDED:
        return response_success(
            message="Платёж уже обработан",
            payment_id=str(payment.id),
        )

    if payment.status != PaymentStatus.PENDING:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="INVALID_PAYMENT_STATUS",
            message=f"Платёж находится в статусе {payment.status.value}",
        )

    try:
        await fake_pay(db_session, payment_id=payment_id, user_id=user_id)

        # Subscription replacement happens only after payment success.
        await deactivate_active_subscriptions(db_session, user_id)
        new_subscription = await create_subscription(
            session=db_session,
            user_id=user_id,
            tariff_id=UUID(str(payment.tariff_id)),
        )

        return response_success(
            payment_id=str(payment.id),
            payment_status=payment.status.value,
            subscription_id=str(new_subscription.id),
        )
    except Exception:
        # Do not expose provider/internal exception details to the client.
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        raise
