from datetime import datetime

from sqlalchemy.dialects.postgresql import insert

from models.wb_stock import WbStock


async def save_stocks(session, user_id, token_id, data):
    stmt = insert(WbStock).values([
        {
            "user_id": user_id,
            "token_id": token_id,
            "nm_id": item["nmId"],
            "barcode": item.get("barcode"),
            "supplier_article": item.get("supplierArticle"),
            "warehouse_name": item["warehouseName"],
            "quantity": item["quantity"],
            "quantity_full": item["quantityFull"],
            "in_way_to_client": item["inWayToClient"],
            "in_way_from_client": item["inWayFromClient"],
            "price": item.get("Price"),
            "discount": item.get("Discount"),
            "category": item.get("category"),
            "subject": item.get("subject"),
            "brand": item.get("brand"),
            "tech_size": item.get("techSize"),
            "is_supply": item.get("isSupply"),
            "is_realization": item.get("isRealization"),
            "sc_code": item.get("SCCode"),
            "last_change_date": item["lastChangeDate"],
        }
        for item in data
    ])

    stmt = stmt.on_conflict_do_update(
        constraint="uq_wb_stock_unique",
        set_={
            "quantity": stmt.excluded.quantity,
            "quantity_full": stmt.excluded.quantity_full,
            "in_way_to_client": stmt.excluded.in_way_to_client,
            "in_way_from_client": stmt.excluded.in_way_from_client,
            "price": stmt.excluded.price,
            "discount": stmt.excluded.discount,
            "last_change_date": stmt.excluded.last_change_date,
            "updated_at": datetime.utcnow(),
        }
    )

    await session.execute(stmt)