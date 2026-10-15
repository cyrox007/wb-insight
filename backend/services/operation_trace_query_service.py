from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.operation_log_event import OperationLogEvent


async def _parent_operation_id(
    session: AsyncSession,
    operation_id: UUID,
) -> UUID | None:
    result = await session.execute(
        select(OperationLogEvent.parent_operation_id)
        .where(
            OperationLogEvent.operation_id == operation_id,
            OperationLogEvent.parent_operation_id.is_not(None),
        )
        .order_by(OperationLogEvent.created_at, OperationLogEvent.id)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _root_operation_id(
    session: AsyncSession,
    operation_id: UUID,
    *,
    max_depth: int,
) -> tuple[UUID, set[UUID]]:
    root_id = operation_id
    visited = {operation_id}

    for _ in range(max_depth):
        parent_id = await _parent_operation_id(session, root_id)
        if parent_id is None or parent_id in visited:
            break
        visited.add(parent_id)
        root_id = parent_id

    return root_id, visited


async def get_complete_operation_trace(
    session: AsyncSession,
    operation_id: UUID,
    *,
    max_depth: int = 12,
    max_operations: int = 500,
) -> tuple[UUID, list[UUID], list[OperationLogEvent]]:
    """Возвращает корень, все дочерние операции и их события в хронологии."""

    depth_limit = max(1, min(max_depth, 32))
    operation_limit = max(1, min(max_operations, 2000))
    root_id, ascent_ids = await _root_operation_id(
        session,
        operation_id,
        max_depth=depth_limit,
    )

    known_ids: set[UUID] = {root_id, *ascent_ids}
    frontier: set[UUID] = {root_id}
    expanded: set[UUID] = set()

    for _ in range(depth_limit):
        current = frontier - expanded
        if not current:
            break
        expanded.update(current)

        result = await session.execute(
            select(OperationLogEvent.operation_id)
            .where(OperationLogEvent.parent_operation_id.in_(current))
            .distinct()
        )
        children = set(result.scalars().all())
        if not children:
            break

        available_slots = operation_limit - len(known_ids)
        if available_slots <= 0:
            break
        if len(children - known_ids) > available_slots:
            new_children = sorted(children - known_ids, key=str)[:available_slots]
            children = (children & known_ids) | set(new_children)

        known_ids.update(children)
        frontier = children

    result = await session.execute(
        select(OperationLogEvent)
        .where(OperationLogEvent.operation_id.in_(known_ids))
        .order_by(
            OperationLogEvent.created_at,
            OperationLogEvent.sequence_no.asc().nullslast(),
            OperationLogEvent.id,
        )
    )
    events = list(result.scalars().all())
    return root_id, sorted(known_ids, key=str), events
