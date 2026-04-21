from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from utils.responce_helps import response_error, response_success
from services.payment_service import create_payment, get_payment, mark_payment_succeeded
from services.tariff_service import get_tariff_by_code
from services.subscription_service import create_subscription, deactivate_active_subscriptions, get_active_subscription, cantelled_subscription, activate_subcription


router = APIRouter(prefix="/billing", tags=["Billing"])


@router.post('/create-payment', dependencies=[Depends(auth_middle)])
async def create_payment_handler(request: Request, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    tariff_code: str = (await request.json()).get('tariff_code', '')

    if tariff_code is None or tariff_code == '':
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="VALIDATION_ERROR",
            message="Tariff is required"
        )

    tariff_code = tariff_code.upper()
    if tariff_code == "DEMO":
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="VALIDATION_ERROR",
            message="Demo tariff is not allowed"
        )
    
    user = request.state.user

    tariff = await get_tariff_by_code(db_session, tariff_code)
    
    payment = await create_payment(
        db=db_session,
        user_id=user['sub'],
        tariff_id=cast(UUID, tariff.id),
        amount=tariff.price_rub
    )
    
    current_sub = await get_active_subscription(
        session=db_session,
        user_id=cast(UUID, user['sub'])
    )
    await cantelled_subscription(db_session, current_sub)
    
    """ new_sub = await create_subscription(
        session=db_session, 
        user_id=cast(UUID, user['sub']), 
        tariff_id=cast(UUID, tariff.id)
    ) """

    return response_success(
        payment_id = payment.id,
        payment_amount = str(payment.amount),
        payment_status = payment.status
    )

@router.post('/pay-now', dependencies=[Depends(auth_middle)])
async def pay_now(request: Request, response: Response, db_session: AsyncSession = Depends(get_db_session)):
    payment_id: UUID = (await request.json()).get('payment_id', None)

    if payment_id is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="VALIDATION_ERROR",
            message="Отсутствует payment_id"
        )
    
    payment = await get_payment(db_session, payment_id)

    if not payment:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            code="NOT_FOUND",
            message="Платеж не найден"
        )
    
    if payment.status == "success":
        return response_success(message="Платеж уже обработан")
    
    try:
        # 1. подтверждаем платеж
        await mark_payment_succeeded(db_session, payment, str(payment_id), {})

        # 2. деактивируем старые подписки
        await deactivate_active_subscriptions(db_session, payment.user_id)

        # 3. создаем новую АКТИВНУЮ подписку
        new_sub = await create_subscription(
            session=db_session, 
            user_id=cast(UUID, payment.user_id), 
            tariff_id=cast(UUID, payment.tariff_id)
        )
        
        await db_session.commit()
        return response_success(
            subscription_id=new_sub.id
        )
    
    except Exception as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        await db_session.rollback()
        return response_error(
            code="INTERNAL_SERVER",
            message=str(e)
        )