from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, replace
from uuid import UUID


@dataclass(frozen=True)
class OperationContext:
    """Контекст одной сквозной операции приложения."""

    operation_id: UUID
    request_id: str | None = None
    actor_user_id: UUID | None = None
    sequence_no: int = 0


_operation_context: ContextVar[OperationContext | None] = ContextVar(
    "operation_context",
    default=None,
)


def bind_operation_context(context: OperationContext) -> Token:
    return _operation_context.set(context)


def reset_operation_context(token: Token) -> None:
    _operation_context.reset(token)


def get_operation_context() -> OperationContext | None:
    return _operation_context.get()


def get_operation_id() -> UUID | None:
    context = get_operation_context()
    return context.operation_id if context else None


def get_request_id() -> str | None:
    context = get_operation_context()
    return context.request_id if context else None


def get_actor_user_id() -> UUID | None:
    context = get_operation_context()
    return context.actor_user_id if context else None


def next_operation_sequence() -> int | None:
    """Возвращает следующий номер шага внутри текущей цепочки."""
    context = get_operation_context()
    if context is None:
        return None
    sequence_no = int(context.sequence_no or 0) + 1
    _operation_context.set(replace(context, sequence_no=sequence_no))
    return sequence_no


def bind_actor_user(user_id: UUID | str | None) -> None:
    context = get_operation_context()
    if context is None or user_id is None:
        return

    try:
        normalized = user_id if isinstance(user_id, UUID) else UUID(str(user_id))
    except (TypeError, ValueError):
        return

    if context.actor_user_id == normalized:
        return
    _operation_context.set(replace(context, actor_user_id=normalized))
