from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.access_control import Permission
from core.authorization import require_permission
from core.dependencies import get_db_session
from services.tariff_service import (
    REQUIRED_ACTIVE_LIMITS,
    delete_limit,
    delete_tariff_by_id,
    get_limit,
    get_missing_required_limits,
    get_tariff_by_code,
    get_tariff_by_id,
    get_tariff_limits_by_id,
    get_tariffs_list,
    insert_tariff,
    is_system_tariff,
    normalized_tariff_code,
    update_limit,
    update_tariff,
    upsert_limit,
    validate_limit_value,
)
from utils.responce_helps import response_error, response_success


router = APIRouter(
    prefix="/control-panel/tariffs",
    tags=["Тарифы"],
    dependencies=[Depends(require_permission(Permission.TARIFFS_READ))],
)


def _parse_price(value) -> Decimal:
    cleaned = str(value).strip().replace(",", ".")
    try:
        price = Decimal(cleaned).quantize(Decimal("0.00"))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("Цена тарифа должна быть числом") from exc
    if not price.is_finite() or price < 0:
        raise ValueError("Цена тарифа не может быть отрицательной")
    return price


@router.get("/")
async def get_tariffs(db_session: AsyncSession = Depends(get_db_session)):
    tariffs = await get_tariffs_list(db_session)
    return response_success(tariffs=tariffs)


@router.get("/{tariff_id}")
async def get_tariff(
    tariff_id: UUID,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    tariff = await get_tariff_by_id(db_session, tariff_id)
    if not tariff:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            code="TARIFF_NOT_FOUND",
            message="Тариф не найден",
        )

    limits = await get_tariff_limits_by_id(db_session, tariff.id)
    return response_success(tariff=tariff, limits=limits)


@router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(Permission.TARIFFS_WRITE))],
)
async def create_tariffs(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    formdata = await request.json()

    code = str(formdata.get("code") or "").strip()
    name = str(formdata.get("name") or "").strip()
    description = str(formdata.get("description") or "")
    is_active = formdata.get("isActive", False)

    if not code:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="CODE_NONE", message="Код тарифа обязателен")

    if not name:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="NAME_NONE", message="Название тарифа обязательно")

    if not isinstance(is_active, bool):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="TARIFF_STATUS_INVALID",
            message="Статус тарифа должен быть логическим значением",
        )

    normalized_code = normalized_tariff_code(code.replace(" ", "_"))
    if normalized_code == "demo":
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="SYSTEM_TARIFF_RESERVED",
            message="Тариф demo является системным и создаётся автоматически",
        )

    if is_active:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="TARIFF_LIMITS_REQUIRED",
            message=(
                "Сначала создайте тариф неактивным, настройте обязательные лимиты, "
                "затем активируйте его"
            ),
        )

    code = normalized_code.upper()
    existing = await get_tariff_by_code(db_session, code)
    if existing is not None:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="TARIFF_EXISTS",
            message="Тариф с таким кодом уже существует",
        )

    try:
        price_rub = _parse_price(formdata.get("price", "0.00"))
    except ValueError as exc:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="PRICE_INVALID", message=str(exc))

    tariff = await insert_tariff(
        db_session,
        {
            "code": code,
            "name": name,
            "description": description,
            "price_rub": price_rub,
            "is_active": False,
            "is_public": False,
        },
    )
    if tariff is None:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="SYSTEM_TARIFF_RESERVED",
            message="Зарезервированный системный тариф нельзя создать вручную",
        )

    return response_success(tariff=tariff)


@router.put(
    "/{tariff_id}/update-status",
    dependencies=[Depends(require_permission(Permission.TARIFFS_WRITE))],
)
async def update_tariff_status(
    tariff_id: str,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    try:
        parsed_tariff_id = UUID(tariff_id)
    except ValueError:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="TARIFF_ID_INVALID",
            message="Некорректный идентификатор тарифа",
        )

    data = await request.json()
    new_status = data.get("status")
    if not isinstance(new_status, bool):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="TARIFF_STATUS_INVALID",
            message="Статус тарифа должен быть логическим значением",
        )

    tariff = await get_tariff_by_id(db_session, parsed_tariff_id)
    if not tariff:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            code="TARIFF_NOT_FOUND",
            message="Тариф не найден",
        )

    if is_system_tariff(tariff) and not new_status:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="SYSTEM_TARIFF_PROTECTED",
            message="Системный тариф demo нельзя деактивировать",
        )

    if new_status:
        missing_limits = await get_missing_required_limits(db_session, tariff.id)
        if missing_limits:
            response.status_code = status.HTTP_409_CONFLICT
            return response_error(
                code="TARIFF_LIMITS_INCOMPLETE",
                message="Нельзя активировать тариф без обязательных лимитов работы системы",
                missing_limits=missing_limits,
            )

    if tariff.is_active == new_status:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="TARIFF_STATUS_NOT_CHANGED",
            message="Статус тарифа не изменился",
        )

    updated = await update_tariff(
        session=db_session,
        tariff=tariff,
        tariff_data={
            "is_active": new_status,
            **({"is_public": False} if not new_status else {}),
        },
    )
    if updated is None:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="SYSTEM_TARIFF_PROTECTED",
            message="Изменение системного тарифа отклонено",
        )

    return response_success(tariff=updated)


@router.put(
    "/{tariff_id}/edit",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_permission(Permission.TARIFFS_WRITE))],
)
async def edit_tariff(
    tariff_id: UUID,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    input_data = await request.json()
    tariff = await get_tariff_by_id(db_session, tariff_id)

    if not tariff:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            code="TARIFF_NOT_FOUND",
            message="Тариф не найден",
        )

    allowed_fields = {"name", "description", "price_rub", "is_active", "is_public"}
    update_data = {key: value for key, value in input_data.items() if key in allowed_fields}

    if "price_rub" in update_data:
        try:
            update_data["price_rub"] = _parse_price(update_data["price_rub"])
        except ValueError as exc:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return response_error(code="PRICE_INVALID", message=str(exc))

    for field in ("is_active", "is_public"):
        if field in update_data and not isinstance(update_data[field], bool):
            response.status_code = status.HTTP_400_BAD_REQUEST
            return response_error(
                code="TARIFF_FLAG_INVALID",
                message=f"Поле {field} должно быть логическим значением",
            )

    if is_system_tariff(tariff):
        requested_price = update_data.get("price_rub", tariff.price_rub)
        requested_active = update_data.get("is_active", tariff.is_active)
        requested_public = update_data.get("is_public", tariff.is_public)
        if (
            Decimal(str(requested_price)) != Decimal("0.00")
            or not requested_active
            or requested_public
        ):
            response.status_code = status.HTTP_409_CONFLICT
            return response_error(
                code="SYSTEM_TARIFF_PROTECTED",
                message=(
                    "Для demo обязательны цена 0 ₽, активный статус "
                    "и скрытие из публичного каталога"
                ),
            )

    target_active = update_data.get("is_active", tariff.is_active)
    target_public = update_data.get("is_public", tariff.is_public)

    if target_public and not target_active:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="TARIFF_PUBLIC_REQUIRES_ACTIVE",
            message="Публичный тариф должен быть активным",
        )

    if target_active:
        missing_limits = await get_missing_required_limits(db_session, tariff.id)
        if missing_limits:
            response.status_code = status.HTTP_409_CONFLICT
            return response_error(
                code="TARIFF_LIMITS_INCOMPLETE",
                message="Активный тариф должен содержать обязательные лимиты работы системы",
                missing_limits=missing_limits,
            )

    updated = await update_tariff(db_session, tariff, update_data)
    if updated is None:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="SYSTEM_TARIFF_PROTECTED",
            message="Изменение системного тарифа отклонено",
        )

    return response_success(tariff=updated)


@router.delete(
    "/{tariff_id}",
    dependencies=[Depends(require_permission(Permission.TARIFFS_WRITE))],
)
async def delete_tariff(
    tariff_id: UUID,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    tariff = await get_tariff_by_id(db_session, tariff_id)
    if not tariff:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="TARIFF_NOT_FOUND", message="Тариф не найден")

    if is_system_tariff(tariff):
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="SYSTEM_TARIFF_PROTECTED",
            message="Системный тариф demo нельзя удалить",
        )

    deleted = await delete_tariff_by_id(db_session, tariff_id)
    if not deleted:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="TARIFF_NOT_DELETED",
            message="Тариф не удалён",
        )

    return response_success(deleting=True)


@router.post(
    "/{tariff_id}/limits/create",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_permission(Permission.TARIFFS_WRITE))],
)
async def create_tariff_limit(
    tariff_id: UUID,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    insert_data = await request.json()
    if not insert_data:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="TARIFF_LIMITS_DATA_NONE",
            message="Данные лимита тарифа обязательны",
        )

    tariff = await get_tariff_by_id(db_session, tariff_id)
    if not tariff:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="TARIFF_NOT_FOUND", message="Тариф не найден")

    limit_type_value = str(insert_data.get("limit_type") or "").strip()
    try:
        limit_value = int(insert_data.get("limit_value", 0))
        validate_limit_value(limit_type_value, limit_value)
    except (TypeError, ValueError) as exc:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="LIMIT_VALUE_INVALID", message=str(exc))

    new_limit = await upsert_limit(
        session=db_session,
        tariff_id=tariff_id,
        limit={
            "limit_type": limit_type_value,
            "limit_value": limit_value,
        },
    )

    return response_success(limit=new_limit)


@router.put(
    "/{tariff_id}/limits/{limit_type}/edit",
    dependencies=[Depends(require_permission(Permission.TARIFFS_WRITE))],
)
async def edit_tariff_limit(
    tariff_id: UUID,
    limit_type: str,
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    if not limit_type:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="LIMIT_TYPE_NONE",
            message="Тип лимита обязателен",
        )

    input_data = await request.json()
    if not input_data or "limit_value" not in input_data:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="TARIFF_LIMITS_DATA_NONE",
            message="Значение лимита обязательно",
        )

    limit = await get_limit(
        session=db_session,
        tariff_id=tariff_id,
        limit_type=limit_type,
    )
    if not limit:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            code="LIMIT_NOT_FOUND",
            message="Лимит не найден",
        )

    try:
        validate_limit_value(limit_type, int(input_data["limit_value"]))
    except (TypeError, ValueError) as exc:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(code="LIMIT_VALUE_INVALID", message=str(exc))

    updated = await update_limit(
        session=db_session,
        limit=limit,
        limit_data=input_data,
    )
    return response_success(limit=updated)


@router.delete(
    "/{tariff_id}/limits/{limit_type}/delete",
    dependencies=[Depends(require_permission(Permission.TARIFFS_WRITE))],
)
async def delete_tariff_limit(
    tariff_id: UUID,
    limit_type: str,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    if not limit_type:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="LIMIT_TYPE_NONE",
            message="Тип лимита обязателен",
        )

    limit = await get_limit(
        session=db_session,
        tariff_id=tariff_id,
        limit_type=limit_type,
    )
    if not limit:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            code="LIMIT_NOT_FOUND",
            message="Лимит не найден",
        )

    tariff = await get_tariff_by_id(db_session, tariff_id)
    if not tariff:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(code="TARIFF_NOT_FOUND", message="Тариф не найден")

    if tariff.is_active and limit_type in REQUIRED_ACTIVE_LIMITS:
        response.status_code = status.HTTP_409_CONFLICT
        return response_error(
            code="REQUIRED_TARIFF_LIMIT_PROTECTED",
            message=(
                "Обязательный лимит нельзя удалить у активного тарифа; "
                "измените его значение"
            ),
        )

    await delete_limit(db_session, limit)
    return response_success(deleting=True)
