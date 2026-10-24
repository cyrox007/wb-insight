from datetime import date
from uuid import uuid4

import pytest

from services.cost_price_service import upsert_cost_prices


class _СессияБезЗапросов:
    async def execute(self, statement):
        raise AssertionError("SQL не должен выполняться для ошибочного пакета")


@pytest.mark.asyncio
async def test_duplicate_sku_and_date_rejected_before_sql():
    items = [
        {"nm_id": 123, "effective_from": "2026-10-01", "cost_price": "10.00"},
        {"nm_id": 123, "effective_from": date(2026, 10, 1), "cost_price": "11.00"},
    ]
    with pytest.raises(ValueError, match="Дубликат себестоимости: артикул 123"):
        await upsert_cost_prices(_СессияБезЗапросов(), uuid4(), items)


@pytest.mark.asyncio
async def test_duplicate_default_date_rejected_before_sql():
    items = [
        {"nm_id": 123, "cost_price": "10.00"},
        {"nm_id": 123, "cost_price": "11.00"},
    ]
    with pytest.raises(ValueError, match="Дубликат себестоимости"):
        await upsert_cost_prices(_СессияБезЗапросов(), uuid4(), items)


@pytest.mark.asyncio
async def test_distinct_dates_are_not_considered_duplicates():
    items = [
        {"nm_id": 123, "effective_from": "2026-10-01", "cost_price": "10.00"},
        {"nm_id": 123, "effective_from": "2026-10-02", "cost_price": "11.00"},
    ]
    with pytest.raises(AssertionError, match="SQL не должен"):
        await upsert_cost_prices(_СессияБезЗапросов(), uuid4(), items)
