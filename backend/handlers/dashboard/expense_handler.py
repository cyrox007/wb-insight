from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from models.manual_expense import ManualExpense
from services.dashboard.account_scope import (
    DashboardAccountUnavailableError,
    resolve_dashboard_scope,
)
from services.manual_expense_service import (
    get_manual_expense,
    list_manual_expenses,
    parse_expense_amount,
)
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/dashboard/expenses", tags=["Expenses"])


def _parse_date(value, *, default: date | None = None) -> date:
    if value in (None, ""):
        if default is None:
            raise ValueError("Дата обязательна")
        return default
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _serialize(expense: ManualExpense) -> dict:
    return {
        "id": str(expense.id),
        "token_id": str(expense.token_id),
        "date": expense.date.isoformat(),
        "category": expense.category,
        "amount": float(expense.amount),
        "currency": expense.currency,
        "nm_id": expense.nm_id,
        "description": expense.description,
    }


async def _specific_scope(
    session: AsyncSession,
    user_id: UUID,
    token_id: UUID,
):
    try:
        return await resolve_dashboard_scope(session, user_id, token_id)
    except DashboardAccountUnavailableError as exc:
        raise ValueError(str(exc)) from exc


@router.get("/", dependencies=[Depends(auth_middle)])
async def get_expenses(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
    start_date: date | None = None,
    end_date: date | None = None,
    token_id: UUID | None = None,
):
    end_date = end_date or date.today()
    start_date = start_date or (end_date - timedelta(days=29))
    if end_date < start_date:
        return response_error(message="Некорректный период", code="INVALID_PERIOD")

    user_id = UUID(str(request.state.user["sub"]))
    try:
        scope = await resolve_dashboard_scope(db_session, user_id, token_id)
    except DashboardAccountUnavailableError as exc:
        return response_error(message=str(exc), code="ACCOUNT_NOT_AVAILABLE")

    items = await list_manual_expenses(
        db_session,
        user_id,
        start_date,
        end_date,
        scope,
    )
    return response_success(
        data={
            "items": [_serialize(item) for item in items],
            "total": len(items),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
    )


@router.post("/", dependencies=[Depends(auth_middle)])
async def create_expense(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
):
    payload = await request.json()
    user_id = UUID(str(request.state.user["sub"]))
    try:
        token_id = UUID(str(payload.get("token_id")))
        scope = await _specific_scope(db_session, user_id, token_id)
        if scope.selected_token_id != token_id:
            raise ValueError("Кабинет недоступен")
        expense_date = _parse_date(payload.get("date"))
        amount = parse_expense_amount(payload.get("amount"))
        category = str(payload.get("category") or "").strip()
        if not category or len(category) > 100:
            raise ValueError("Укажите категорию расхода")
        nm_id_raw = payload.get("nm_id")
        nm_id = int(nm_id_raw) if nm_id_raw not in (None, "") else None
        if nm_id is not None and nm_id <= 0:
            raise ValueError("Некорректный артикул WB")
    except (TypeError, ValueError) as exc:
        return response_error(message=str(exc), code="INVALID_EXPENSE")

    expense = ManualExpense(
        user_id=user_id,
        token_id=token_id,
        date=expense_date,
        category=category,
        amount=amount,
        currency=str(payload.get("currency") or "RUB").upper(),
        nm_id=nm_id,
        description=(str(payload.get("description")).strip() if payload.get("description") else None),
    )
    db_session.add(expense)
    await db_session.flush()
    return response_success(data=_serialize(expense), message="Расход добавлен")


@router.put("/{expense_id}", dependencies=[Depends(auth_middle)])
async def update_expense(
    expense_id: UUID,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
):
    payload = await request.json()
    user_id = UUID(str(request.state.user["sub"]))
    expense = await get_manual_expense(db_session, user_id, expense_id)
    if expense is None:
        return response_error(message="Расход не найден", code="NOT_FOUND")

    try:
        token_id = UUID(str(payload.get("token_id", expense.token_id)))
        await _specific_scope(db_session, user_id, token_id)
        expense.token_id = token_id
        if "date" in payload:
            expense.date = _parse_date(payload.get("date"))
        if "amount" in payload:
            expense.amount = parse_expense_amount(payload.get("amount"))
        if "category" in payload:
            category = str(payload.get("category") or "").strip()
            if not category or len(category) > 100:
                raise ValueError("Укажите категорию расхода")
            expense.category = category
        if "currency" in payload:
            expense.currency = str(payload.get("currency") or "RUB").upper()
        if "nm_id" in payload:
            nm_raw = payload.get("nm_id")
            expense.nm_id = int(nm_raw) if nm_raw not in (None, "") else None
            if expense.nm_id is not None and expense.nm_id <= 0:
                raise ValueError("Некорректный артикул WB")
        if "description" in payload:
            expense.description = (
                str(payload.get("description")).strip()
                if payload.get("description")
                else None
            )
    except (TypeError, ValueError) as exc:
        return response_error(message=str(exc), code="INVALID_EXPENSE")

    await db_session.flush()
    return response_success(data=_serialize(expense), message="Расход обновлён")


@router.delete("/{expense_id}", dependencies=[Depends(auth_middle)])
async def delete_expense(
    expense_id: UUID,
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
):
    user_id = UUID(str(request.state.user["sub"]))
    expense = await get_manual_expense(db_session, user_id, expense_id)
    if expense is None:
        return response_error(message="Расход не найден", code="NOT_FOUND")

    try:
        await _specific_scope(db_session, user_id, expense.token_id)
    except ValueError as exc:
        return response_error(message=str(exc), code="ACCOUNT_NOT_AVAILABLE")

    await db_session.delete(expense)
    return response_success(message="Расход удалён")
