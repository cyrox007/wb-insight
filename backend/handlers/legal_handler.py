from fastapi import APIRouter, Response, status

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
