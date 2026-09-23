import csv
import io
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, Response, UploadFile, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from models.product_cost_price_history import ProductCostPriceHistory
from models.product_cost_price_model import ProductCostPrice
from services.cost_price_service import (
    calculate_unit_economy,
    get_dashboard_unit_economy,
    get_product_list_with_costs,
    upsert_cost_prices,
)
from utils.request_payload import request_json_object
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/cost-prices", tags=["cost_prices"])


def _user_id(request: Request) -> UUID:
    return UUID(str(request.state.user["sub"]))


@router.get("/unit-economy", dependencies=[Depends(auth_middle)])
async def get_unit_economy(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    nm_id: Optional[int] = None,
):
    end_date = end_date or date.today()
    start_date = start_date or end_date - timedelta(days=29)
    if end_date < start_date:
        return response_error(message="Некорректный период", code="INVALID_PERIOD")

    user_id = _user_id(request)
    if nm_id:
        metrics = await calculate_unit_economy(
            session=db_session,
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            nm_id=nm_id,
        )
        if not metrics:
            return response_error(message="Нет данных за указанный период", code="NO_DATA")
        return response_success(data=metrics)

    metrics = await get_dashboard_unit_economy(
        session=db_session,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
    )
    return response_success(data=metrics)


@router.get("/products", dependencies=[Depends(auth_middle)])
async def get_products_with_costs(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    limit: int = 100,
    offset: int = 0,
):
    end_date = end_date or date.today()
    start_date = start_date or end_date - timedelta(days=29)
    if end_date < start_date:
        return response_error(message="Некорректный период", code="INVALID_PERIOD")

    products, total_count = await get_product_list_with_costs(
        session=db_session,
        user_id=_user_id(request),
        start_date=start_date,
        end_date=end_date,
        limit=max(1, min(limit, 500)),
        offset=max(0, offset),
    )
    return response_success(
        data={
            "items": products,
            "total": total_count,
            "limit": limit,
            "offset": offset,
        }
    )


@router.post("/upload", dependencies=[Depends(auth_middle)])
async def upload_cost_prices(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    file: Optional[UploadFile] = File(None),
):
    if not file:
        return response_error(message="Файл не предоставлен", code="NO_FILE")

    try:
        content = await file.read()
        content_str = content.decode("utf-8-sig")
        items = []
        for row in csv.DictReader(io.StringIO(content_str)):
            try:
                nm_id = int(row.get("nm_id") or 0)
                cost_price = float(row.get("cost_price") or 0)
                if nm_id <= 0 or cost_price < 0:
                    continue
                items.append(
                    {
                        "nm_id": nm_id,
                        "seller_sku": row.get("seller_sku"),
                        "product_name": row.get("product_name"),
                        "cost_price": cost_price,
                        "currency": row.get("currency") or "RUB",
                        "comment": row.get("comment"),
                        "effective_from": row.get("effective_from") or None,
                    }
                )
            except (TypeError, ValueError):
                continue

        if not items:
            return response_error(message="Нет валидных данных в файле", code="INVALID_DATA")

        count = await upsert_cost_prices(
            session=db_session,
            user_id=_user_id(request),
            items=items,
        )
        return response_success(
            message=f"Успешно загружено {count} строк себестоимости",
            data={"uploaded_count": count},
        )
    except (UnicodeDecodeError, ValueError) as exc:
        return response_error(message=str(exc), code="FILE_ERROR")


@router.post("/batch", dependencies=[Depends(auth_middle)])
async def batch_update_cost_prices(
    request: Request,
    response: Response,
    db_session: AsyncSession = Depends(get_db_session),
):
    payload = await request_json_object(request)
    if payload is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="REQUEST_PAYLOAD_INVALID",
            message="Ожидается JSON-объект себестоимости",
        )

    raw_items = payload.get("items")
    if raw_items is not None and not isinstance(raw_items, list):
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(
            code="INVALID_DATA",
            message="Поле items должно быть списком",
        )

    items = raw_items or []
    if not items:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(message="Список товаров пуст", code="EMPTY_LIST")

    try:
        count = await upsert_cost_prices(
            session=db_session,
            user_id=_user_id(request),
            items=items,
        )
    except (TypeError, ValueError) as exc:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return response_error(message=str(exc), code="INVALID_DATA")

    return response_success(
        message=f"Успешно обновлено {count} строк себестоимости",
        data={"updated_count": count},
    )


@router.delete("/{nm_id}", dependencies=[Depends(auth_middle)])
async def delete_cost_price(
    request: Request,
    nm_id: int,
    db_session: AsyncSession = Depends(get_db_session),
):
    user_id = _user_id(request)
    snapshot_result = await db_session.execute(
        delete(ProductCostPrice)
        .where(ProductCostPrice.user_id == user_id, ProductCostPrice.nm_id == nm_id)
        .returning(ProductCostPrice.id)
    )
    deleted_id = snapshot_result.scalar_one_or_none()
    if deleted_id is None:
        return response_error(message="Запись не найдена", code="NOT_FOUND")

    await db_session.execute(
        delete(ProductCostPriceHistory).where(
            ProductCostPriceHistory.user_id == user_id,
            ProductCostPriceHistory.nm_id == nm_id,
        )
    )
    return response_success(message="Себестоимость и её история удалены")
