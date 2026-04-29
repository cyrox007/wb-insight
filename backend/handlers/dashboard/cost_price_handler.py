import io
from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from models.product_cost_price_model import ProductCostPrice

from services.cost_price_service import (
    calculate_unit_economy,
    get_dashboard_unit_economy,
    get_product_list_with_costs,
    upsert_cost_prices,
)
from utils.responce_helps import response_error, response_success

router = APIRouter(prefix="/cost-prices", tags=["cost_prices"])


@router.get("/unit-economy", dependencies=[Depends(auth_middle)])
async def get_unit_economy(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    nm_id: Optional[int] = None,
):
    """
    Получить метрики unit-экономики

    Формулы:
    - profit = ppvz_for_pay - (cost_price × quantity)
    - margin = profit / retail_amount × 100
    - DRR = (commission + logistics + penalty) / retail_amount × 100
    """
    from datetime import timedelta, timezone

    end_date = end_date if end_date is not None else date.today()
    start_date = start_date if start_date is not None else end_date - timedelta(days=30)

    current_user = request.state.user

    if nm_id:
        # Метрики для конкретного товара
        metrics = await calculate_unit_economy(
            session=db_session,
            user_id=current_user['sub'],
            start_date=start_date,
            end_date=end_date,
            nm_id=nm_id
        )

        if not metrics:
            return response_error(
                message="Нет данных за указанный период",
                code="NO_DATA"
            )

        return response_success(data=metrics)
    else:
        # Агрегированные метрики для дашборда
        metrics = await get_dashboard_unit_economy(
            session=db_session,
            user_id=current_user['sub'],
            start_date=start_date,
            end_date=end_date
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
    """
    Получить список товаров с метриками и себестоимостью
    """
    from datetime import timedelta, timezone

    end_date = end_date if end_date is not None else date.today()
    start_date = start_date if start_date is not None else end_date - timedelta(days=30)

    current_user = request.state.user

    products, total_count = await get_product_list_with_costs(
        session=db_session,
        user_id=current_user['sub'],
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset
    )

    return response_success(
        data={
            'items': products,
            'total': total_count,
            'limit': limit,
            'offset': offset
        }
    )


@router.post("/upload", dependencies=[Depends(auth_middle)])
async def upload_cost_prices(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    file: Optional[UploadFile] = File(None),
):
    """
    Загрузить себестоимость из CSV/Excel файла

    Ожидаемый формат CSV:
    nm_id,seller_sku,product_name,cost_price,comment
    12345678,ART-001,Товар 1,1500.00,Комментарий
    """
    import csv
    from decimal import Decimal

    current_user = request.state.user

    if not file:
        return response_error(
            message="Файл не предоставлен",
            code="NO_FILE"
        )

    try:
        content = await file.read()
        content_str = content.decode('utf-8')

        items = []
        reader = csv.DictReader(io.StringIO(content_str))

        for row in reader:
            try:
                item = {
                    'nm_id': int(row.get('nm_id', 0)),
                    'seller_sku': row.get('seller_sku'),
                    'product_name': row.get('product_name'),
                    'cost_price': float(row.get('cost_price', 0)),
                    'comment': row.get('comment')
                }

                if item['nm_id'] <= 0 or item['cost_price'] < 0:
                    continue

                items.append({
                    'nm_id': item.get('nm_id'),
                    'seller_sku': item.get('seller_sku'),
                    'product_name': item.get('product_name'),
                    'cost_price': item.get('cost_price'),
                    'currency': 'RUB',
                    'comment': item.get('comment')
                })
            except (ValueError, TypeError) as e:
                continue

        if not items:
            return response_error(
                message="Нет валидных данных в файле",
                code="INVALID_DATA"
            )

        count = await upsert_cost_prices(
            session=db_session,
            user_id=current_user['sub'],
            items=items
        )

        return response_success(
            message=f"Успешно загружено {count} товаров",
            data={'uploaded_count': count}
        )

    except Exception as e:
        return response_error(
            message=f"Ошибка обработки файла: {str(e)}",
            code="FILE_ERROR"
        )


@router.post("/batch", dependencies=[Depends(auth_middle)])
async def batch_update_cost_prices(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
):
    """
    Массовое обновление себестоимости через JSON

    Пример запроса:
    {
        "items": [
            {
                "nm_id": 12345678,
                "seller_sku": "ART-001",
                "cost_price": 1500.00,
                "comment": "Поставщик А"
            }
        ]
    }
    """
    payload: dict = await request.json()
    current_user = request.state.user

    if not payload.get('items'):
        return response_error(
            message="Список товаров пуст",
            code="EMPTY_LIST"
        )
        

    count = await upsert_cost_prices(
        session=db_session,
        user_id=current_user['sub'],
        items=list(payload.get('items', []))
    )

    return response_success(
        message=f"Успешно обновлено {count} товаров",
        data={'updated_count': count}
    )


@router.delete("/{nm_id}", dependencies=[Depends(auth_middle)])
async def delete_cost_price(
    request: Request,
    nm_id: int,
    db_session: AsyncSession = Depends(get_db_session),
):
    """
    Удалить себестоимость для конкретного товара
    """
    from sqlalchemy import delete

    current_user = request.state.user

    query = delete(ProductCostPrice).where(
        ProductCostPrice.user_id == current_user['sub'],
        ProductCostPrice.nm_id == nm_id
    )

    result = await db_session.execute(query)
    deleted = result.fetchall()

    await db_session.commit()

    if not deleted:
        return response_error(
            message="Запись не найдена",
            code="NOT_FOUND"
        )

    return response_success(message="Себестоимость удалена")