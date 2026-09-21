from collections.abc import Sequence
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import setup_logger
from models.tariffs_model import TariffLimit, TariffPlan


logger = setup_logger(__name__)

SYSTEM_TARIFF_CODES = frozenset({"demo"})
REQUIRED_ACTIVE_LIMITS: dict[str, int] = {
    "wb_accounts": 1,
    "sync_frequency_hours": 1,
}


def normalized_tariff_code(value: str | None) -> str:
    return str(value or "").strip().lower()


def is_system_tariff(tariff: TariffPlan) -> bool:
    return normalized_tariff_code(tariff.code) in SYSTEM_TARIFF_CODES


def validate_limit_value(limit_type: str, limit_value: int) -> None:
    normalized_type = str(limit_type or "").strip()
    if not normalized_type:
        raise ValueError("Тип лимита обязателен")

    numeric_value = int(limit_value)
    if numeric_value < 0:
        raise ValueError("Значение лимита не может быть отрицательным")

    minimum = REQUIRED_ACTIVE_LIMITS.get(normalized_type)
    if minimum is not None and numeric_value < minimum:
        raise ValueError(
            f"Лимит {normalized_type} для активного тарифа должен быть не меньше {minimum}"
        )


async def get_missing_required_limits(
    session: AsyncSession,
    tariff_id: UUID,
) -> list[str]:
    limits = await get_tariff_limits_by_id(session, tariff_id)
    values = {item.limit_type: int(item.limit_value) for item in limits}

    return [
        limit_type
        for limit_type, minimum in REQUIRED_ACTIVE_LIMITS.items()
        if values.get(limit_type, 0) < minimum
    ]


async def insert_tariff(
    session: AsyncSession,
    tariff,
) -> Optional[TariffPlan]:
    if normalized_tariff_code(tariff.get("code")) in SYSTEM_TARIFF_CODES:
        logger.warning("Refusing to create reserved system tariff code=%s", tariff.get("code"))
        return None

    new_tariff = TariffPlan(
        code=tariff["code"],
        name=tariff["name"],
        description=tariff["description"],
        price_rub=tariff["price_rub"],
        is_active=tariff["is_active"],
        is_public=tariff.get("is_public", True),
    )

    try:
        session.add(new_tariff)
        await session.flush()
        return new_tariff
    except IntegrityError:
        await session.rollback()
        logger.warning("Tariff with code %s already exists", tariff["code"])
        return None
    except Exception as exc:
        logger.error("Error inserting tariff: %s", exc)
        return None


async def get_tariffs_list(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 10,
    **kwargs,
) -> Sequence[TariffPlan]:
    query = select(TariffPlan).offset(offset).limit(limit)
    if only_active := kwargs.get("only_active"):
        query = query.where(TariffPlan.is_active == only_active)

    if only_public := kwargs.get("only_public"):
        query = query.where(TariffPlan.is_public == only_public)

    result = await session.execute(query)
    return result.scalars().all()


async def get_tariff_by_id(
    session: AsyncSession,
    tariff_id: UUID,
) -> Optional[TariffPlan]:
    query = select(TariffPlan).where(TariffPlan.id == tariff_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_tariff_by_code(
    session: AsyncSession,
    code: str,
) -> Optional[TariffPlan]:
    query = select(TariffPlan).where(
        func.lower(TariffPlan.code) == normalized_tariff_code(code)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def update_tariff(
    session: AsyncSession,
    tariff: TariffPlan,
    tariff_data: dict,
) -> Optional[TariffPlan]:
    try:
        if is_system_tariff(tariff):
            requested_price = tariff_data.get("price_rub", tariff.price_rub)
            requested_active = tariff_data.get("is_active", tariff.is_active)
            requested_public = tariff_data.get("is_public", tariff.is_public)
            if (
                float(requested_price) != 0.0
                or not bool(requested_active)
                or bool(requested_public)
            ):
                logger.warning("Refusing unsafe update of system demo tariff")
                return None

        for key, value in tariff_data.items():
            if hasattr(tariff, key):
                setattr(tariff, key, value)

        session.add(tariff)
        await session.flush()
        return tariff
    except Exception as exc:
        logger.error("Error updating tariff: %s", exc)
        return None


async def get_tariff_limits_by_id(
    session: AsyncSession,
    tariff_id: UUID,
) -> Sequence[TariffLimit]:
    query = select(TariffLimit).where(TariffLimit.tariff_id == tariff_id)
    result = await session.execute(query)
    return result.scalars().all()


async def delete_tariff_by_id(
    session: AsyncSession,
    tariff_id: UUID,
) -> bool:
    try:
        tariff = await get_tariff_by_id(session, tariff_id)
        if tariff is None or is_system_tariff(tariff):
            return False

        query = delete(TariffPlan).where(TariffPlan.id == tariff_id)
        await session.execute(query)
        return True
    except Exception as exc:
        logger.error("Error deleting tariff: %s", exc)
        return False


async def get_public_runtime_ready_tariffs(
    session: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 10,
) -> list[TariffPlan]:
    tariffs = await get_tariffs_list(
        session,
        offset=offset,
        limit=limit,
        only_active=True,
        only_public=True,
    )
    ready: list[TariffPlan] = []
    for tariff in tariffs:
        if not await get_missing_required_limits(session, tariff.id):
            ready.append(tariff)
        else:
            logger.warning(
                "Hiding incomplete public tariff code=%s from catalog",
                tariff.code,
            )
    return ready


async def upsert_limit(
    session: AsyncSession,
    tariff_id: UUID,
    limit: dict,
):
    limit_type = str(limit["limit_type"] or "").strip()
    limit_value = int(limit["limit_value"])
    validate_limit_value(limit_type, limit_value)

    existing = await get_limit(session, tariff_id, limit_type)

    if existing:
        existing.limit_value = limit_value
        await session.flush()
        return existing

    new_limit = TariffLimit(
        tariff_id=tariff_id,
        limit_type=limit_type,
        limit_value=limit_value,
    )

    session.add(new_limit)
    await session.flush()
    return new_limit


async def get_limit(
    session: AsyncSession,
    tariff_id: UUID,
    limit_type: str,
) -> Optional[TariffLimit]:
    query = select(TariffLimit).where(
        and_(
            TariffLimit.tariff_id == tariff_id,
            TariffLimit.limit_type == limit_type,
        )
    )

    result = await session.execute(query)
    return result.scalar_one_or_none()


async def update_limit(
    session: AsyncSession,
    limit: TariffLimit,
    limit_data: dict,
) -> Optional[TariffLimit]:
    try:
        if "limit_value" in limit_data:
            validate_limit_value(limit.limit_type, int(limit_data["limit_value"]))

        for key, value in limit_data.items():
            if hasattr(limit, key):
                setattr(limit, key, value)

        session.add(limit)
        await session.flush()
        return limit
    except Exception as exc:
        logger.error("Error updating limit: %s", exc)
        return None


async def delete_limit(
    session: AsyncSession,
    limit: TariffLimit,
) -> bool:
    try:
        await session.delete(limit)
        return True
    except Exception as exc:
        logger.error("Error deleting limit: %s", exc)
        return False
