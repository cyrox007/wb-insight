import hashlib
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import select

from core.database import Database
from core.logger import setup_logger
from core.operation_context import bind_actor_user, get_operation_context
from models.users_model import User
from services.operation_log_service import persist_current_operation_event
from settings import config
from utils.jwt import verify_token


logger = setup_logger(__name__)


async def _load_account_state(user_id: UUID) -> tuple[bool, int] | None:
    async with Database.sessionmaker()() as session:
        result = await session.execute(
            select(User.is_active, User.session_version).where(User.id == user_id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        return bool(row.is_active), int(row.session_version)


def _token_fingerprint(token_value: str) -> str:
    return hashlib.sha256(token_value.encode("utf-8")).hexdigest()


async def _trace_auth_step(
    step: str,
    status_value: str,
    *,
    user_id: UUID | str | None = None,
    severity: str = "info",
    error_code: str | None = None,
    input_data: dict | None = None,
    output_data: dict | None = None,
) -> None:
    if get_operation_context() is None:
        return
    await persist_current_operation_event(
        domain="auth",
        operation="access_session",
        step=step,
        status=status_value,
        severity=severity,
        event_kind="security_decision",
        component="authentication",
        direction="internal",
        user_id=user_id,
        subject_type="user" if user_id else None,
        subject_id=user_id,
        error_code=error_code,
        message=f"Проверка сессии: {step}",
        input_data=input_data or {},
        output_data=output_data or {},
    )


async def auth_middle(request: Request):
    """Проверяет Bearer-токен доступа и версию активной сессии аккаунта."""
    authorization = request.headers.get("authorization", "")
    scheme, separator, token_value = authorization.partition(" ")

    if not separator or scheme.lower() != "bearer" or not token_value.strip():
        await _trace_auth_step(
            "access_token_missing",
            "warning",
            severity="warning",
            error_code="missing_or_invalid_token",
            input_data={"authorization_scheme": scheme or None},
        )
        logger.warning("Отсутствует или некорректен Bearer-токен в HTTP-запросе")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "bad", "error_type": "missing_or_invalid_token"},
        )

    raw_token = token_value.strip()
    fingerprint = _token_fingerprint(raw_token)
    user_data = verify_token(raw_token)
    if (
        not user_data
        or not user_data.get("sub")
        or user_data.get("type") != "access"
    ):
        await _trace_auth_step(
            "access_token_rejected",
            "warning",
            severity="warning",
            error_code="invalid_access_token",
            input_data={"token_fingerprint_sha256": fingerprint},
        )
        logger.warning("Недопустимый access-токен в HTTP-запросе")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "error_type": "invalid_access_token"},
        )

    session_version = user_data.get("sv")
    raw_user_id = user_data.get("sub")
    await _trace_auth_step(
        "access_token_verified",
        "success",
        user_id=raw_user_id,
        input_data={"token_fingerprint_sha256": fingerprint},
        output_data={
            "token_type": user_data.get("type"),
            "session_version": session_version,
            "issued_at": user_data.get("iat"),
            "expires_at": user_data.get("exp"),
        },
    )

    if session_version is None and not config.IS_PRODUCTION:
        request.state.user = user_data
        bind_actor_user(raw_user_id)
        await _trace_auth_step(
            "development_session_accepted",
            "warning",
            user_id=raw_user_id,
            severity="warning",
            output_data={"reason": "Вне production разрешён старый токен без версии сессии"},
        )
        return

    try:
        user_id = UUID(str(raw_user_id))
        token_session_version = int(session_version)
    except (TypeError, ValueError):
        await _trace_auth_step(
            "access_token_claims_invalid",
            "warning",
            user_id=raw_user_id,
            severity="warning",
            error_code="invalid_access_token",
            output_data={"session_version": session_version},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "error_type": "invalid_access_token"},
        )

    account_state = await _load_account_state(user_id)
    if (
        account_state is None
        or not account_state[0]
        or account_state[1] != token_session_version
    ):
        await _trace_auth_step(
            "session_rejected",
            "warning",
            user_id=user_id,
            severity="warning",
            error_code="session_revoked",
            output_data={
                "account_found": account_state is not None,
                "account_active": account_state[0] if account_state else None,
                "token_session_version": token_session_version,
                "current_session_version": account_state[1] if account_state else None,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "error_type": "session_revoked"},
        )

    request.state.user = user_data
    bind_actor_user(user_id)
    await _trace_auth_step(
        "session_verified",
        "success",
        user_id=user_id,
        output_data={
            "account_active": True,
            "session_version": token_session_version,
        },
    )