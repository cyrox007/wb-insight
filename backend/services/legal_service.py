from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
from typing import Iterable
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from models.legal_consent import LegalConsent
from settings import config


class LegalConsentError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class LegalDocument:
    code: str
    version: str
    title: str
    contexts: tuple[str, ...]
    content: str
    approved: bool = False

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    def public_payload(self, *, include_content: bool = False) -> dict:
        payload = {
            "code": self.code,
            "version": self.version,
            "title": self.title,
            "sha256": self.sha256,
            "contexts": list(self.contexts),
            "status": "approved" if self.approved else "draft",
            "legal_review_required": not self.approved,
        }
        if include_content:
            payload["content"] = self.content
        return payload


_DRAFT_NOTICE = (
    "СТАТУС: ЧЕРНОВИК. Документ подготовлен как технический шаблон для продукта "
    "WB Insight и должен быть утверждён владельцем сервиса и юридическим специалистом "
    "до публичного релиза."
)


LEGAL_DOCUMENTS: tuple[LegalDocument, ...] = (
    LegalDocument(
        code="terms",
        version="1.0-draft.1",
        title="Пользовательское соглашение",
        contexts=("registration",),
        content=f"""{_DRAFT_NOTICE}\n\n# Пользовательское соглашение\n\nНастоящий документ определяет базовые условия использования сервиса WB Insight. Пользователь обязан использовать сервис законно, обеспечивать конфиденциальность своих учётных данных и не передавать доступ третьим лицам без соответствующих полномочий.\n\nСервис предоставляет аналитические функции для данных маркетплейсов. Состав функций, тарифы, ограничения и порядок прекращения доступа определяются интерфейсом продукта и действующими коммерческими условиями.\n\nОкончательные реквизиты оператора, применимое право, порядок уведомлений, ответственность сторон и порядок разрешения споров должны быть заполнены и утверждены до публичного релиза.\n""",
    ),
    LegalDocument(
        code="privacy",
        version="1.0-draft.1",
        title="Политика конфиденциальности",
        contexts=("registration", "billing", "marketplace_credential"),
        content=f"""{_DRAFT_NOTICE}\n\n# Политика конфиденциальности\n\nWB Insight обрабатывает данные, необходимые для регистрации, аутентификации, работы аналитики, поддержки, биллинга и обеспечения безопасности. Доступ к данным маркетплейса осуществляется только в объёме, необходимом для функций продукта.\n\nТехнические журналы и доказательства согласия должны храниться с принципом минимизации данных. Чувствительные marketplace credentials не публикуются и должны храниться в зашифрованном виде.\n\nДо релиза необходимо утвердить полный перечень категорий данных, цели и основания обработки, сроки хранения, перечень обработчиков/получателей, порядок реализации прав пользователя и реквизиты оператора.\n""",
    ),
    LegalDocument(
        code="personal_data",
        version="1.0-draft.1",
        title="Согласие на обработку персональных данных",
        contexts=("registration",),
        content=f"""{_DRAFT_NOTICE}\n\n# Согласие на обработку персональных данных\n\nПользователь подтверждает передачу данных, необходимых для создания и обслуживания аккаунта WB Insight, а также для исполнения запрошенных функций сервиса.\n\nДо публичного релиза текст должен быть приведён в соответствие с фактическими целями, категориями данных, сроками хранения и применимыми требованиями законодательства.\n""",
    ),
    LegalDocument(
        code="offer",
        version="1.0-draft.1",
        title="Условия платной подписки / оферта",
        contexts=("billing",),
        content=f"""{_DRAFT_NOTICE}\n\n# Условия платной подписки\n\nПлатная подписка WB Insight активируется только после подтверждения успешной оплаты платёжным провайдером. Цена и срок тарифа отображаются пользователю до перехода к оплате.\n\nДо релиза необходимо утвердить реквизиты продавца услуги, порядок заключения договора, правила продления, прекращения подписки, налогообложение и иные обязательные коммерческие условия.\n""",
    ),
    LegalDocument(
        code="refund_policy",
        version="1.0-draft.1",
        title="Политика отмены и возвратов",
        contexts=("billing",),
        content=f"""{_DRAFT_NOTICE}\n\n# Политика отмены и возвратов\n\nДокумент должен описывать порядок отмены подписки, обращения за возвратом, сроки рассмотрения и применимые ограничения.\n\nКонкретные правила возврата не утверждены и должны быть согласованы владельцем сервиса и юридическим специалистом до публичного релиза.\n""",
    ),
    LegalDocument(
        code="credential_policy",
        version="1.0-draft.1",
        title="Правила подключения доступа к маркетплейсу",
        contexts=("marketplace_credential",),
        content=f"""{_DRAFT_NOTICE}\n\n# Правила подключения доступа к маркетплейсу\n\nПользователь подтверждает, что имеет право подключать указанный кабинет маркетплейса к WB Insight. Для Wildberries сервис требует только поддерживаемый cloud-safe токен с минимально необходимыми Read Only разрешениями. Personal и Test tokens не принимаются для production cloud flow.\n\nCredentials используются для получения аналитических данных, хранятся в зашифрованном виде и не должны отображаться после сохранения. Пользователь может отозвать доступ удалением credential или отзывом токена на стороне маркетплейса.\n\nЮридический текст об обработке credentials и распределении ответственности должен быть утверждён до публичного релиза.\n""",
    ),
)


DOCUMENT_BY_CODE = {document.code: document for document in LEGAL_DOCUMENTS}


def documents_for_context(context: str) -> tuple[LegalDocument, ...]:
    return tuple(
        document for document in LEGAL_DOCUMENTS if context in document.contexts
    )


def get_document(code: str) -> LegalDocument | None:
    return DOCUMENT_BY_CODE.get(code)


def validate_consent_payload(
    payload: object,
    *,
    context: str,
) -> tuple[LegalDocument, ...]:
    required = documents_for_context(context)
    if not required:
        raise LegalConsentError("LEGAL_CONTEXT_UNKNOWN", "Неизвестный контекст согласия")

    if not isinstance(payload, list):
        raise LegalConsentError(
            "LEGAL_CONSENT_REQUIRED",
            "Необходимо принять актуальные обязательные документы",
        )

    accepted: dict[str, dict] = {}
    for item in payload:
        if not isinstance(item, dict) or item.get("accepted") is not True:
            continue
        code = str(item.get("code") or "").strip()
        if code:
            accepted[code] = item

    for document in required:
        item = accepted.get(document.code)
        if item is None:
            raise LegalConsentError(
                "LEGAL_CONSENT_REQUIRED",
                f"Не принято обязательное условие: {document.title}",
            )
        if str(item.get("version") or "") != document.version:
            raise LegalConsentError(
                "LEGAL_DOCUMENT_OUTDATED",
                f"Версия документа «{document.title}» устарела. Обновите страницу.",
            )
        if not hmac.compare_digest(
            str(item.get("sha256") or ""),
            document.sha256,
        ):
            raise LegalConsentError(
                "LEGAL_DOCUMENT_MISMATCH",
                f"Контрольная сумма документа «{document.title}» не совпадает",
            )

    return required


def _evidence_hmac(value: str | None) -> str | None:
    if not value:
        return None
    key = (config.LEGAL_EVIDENCE_HMAC_KEY or config.SECRET_KEY or "").encode("utf-8")
    if not key:
        return None
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


async def record_consents(
    session: AsyncSession,
    *,
    user_id: UUID,
    documents: Iterable[LegalDocument],
    context: str,
    client_ip: str | None,
    user_agent: str | None,
    context_reference: str | None = None,
) -> list[LegalConsent]:
    now = datetime.now(timezone.utc)
    records: list[LegalConsent] = []
    for document in documents:
        record = LegalConsent(
            user_id=user_id,
            document_code=document.code,
            document_version=document.version,
            document_sha256=document.sha256,
            context=context,
            context_reference=context_reference,
            accepted_at=now,
            ip_hmac=_evidence_hmac(client_ip),
            user_agent_hmac=_evidence_hmac(user_agent),
        )
        session.add(record)
        records.append(record)
    await session.flush()
    return records
