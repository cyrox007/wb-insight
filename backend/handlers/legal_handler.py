from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.dependencies import get_db_session
from core.middleware import auth_middle
from models.legal_consent import LegalConsent
from services.legal_service import documents_for_context, get_document
from utils.responce_helps import response_error, response_success


router = APIRouter(prefix="/legal", tags=["Legal"])


@router.get("/requirements/{context}")
async def legal_requirements(context: str, response: Response) -> dict:
    documents = documents_for_context(context)
    if not documents:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            code="LEGAL_CONTEXT_NOT_FOUND",
            message="Неизвестный контекст юридических документов",
        )
    return response_success(
        context=context,
        documents=[document.public_payload() for document in documents],
    )


@router.get("/documents/{code}")
async def legal_document(code: str, response: Response) -> dict:
    document = get_document(code)
    if document is None:
        response.status_code = status.HTTP_404_NOT_FOUND
        return response_error(
            code="LEGAL_DOCUMENT_NOT_FOUND",
            message="Документ не найден",
        )
    return response_success(document=document.public_payload(include_content=True))


@router.get("/consents/me", dependencies=[Depends(auth_middle)])
async def current_user_consents(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return immutable consent evidence for the authenticated user.

    Privacy-sensitive evidence hashes (IP/User-Agent HMAC) are intentionally
    not exposed through the public API.
    """
    user_id = UUID(str(request.state.user["sub"]))
    result = await db_session.execute(
        select(LegalConsent)
        .where(LegalConsent.user_id == user_id)
        .order_by(LegalConsent.accepted_at.asc(), LegalConsent.id.asc())
    )
    records = list(result.scalars().all())
    return response_success(
        consents=[
            {
                "id": str(record.id),
                "document_code": record.document_code,
                "document_version": record.document_version,
                "document_sha256": record.document_sha256,
                "context": record.context,
                "context_reference": record.context_reference,
                "accepted_at": record.accepted_at,
            }
            for record in records
        ]
    )
