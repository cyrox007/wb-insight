import pytest

from services.legal_service import (
    LegalConsentError,
    documents_for_context,
    get_document,
    validate_consent_payload,
)


def _payload_for(context: str) -> list[dict]:
    return [
        {
            "code": document.code,
            "version": document.version,
            "sha256": document.sha256,
            "accepted": True,
        }
        for document in documents_for_context(context)
    ]


def test_registration_requirements_depend_on_entity_type():
    regular = {document.code for document in documents_for_context("registration")}
    legal = {document.code for document in documents_for_context("registration_legal")}

    assert regular == {"terms", "privacy"}
    assert legal == {"terms", "privacy", "personal_data"}


def test_billing_and_marketplace_requirements_are_explicit():
    billing = {document.code for document in documents_for_context("billing")}
    marketplace = {
        document.code for document in documents_for_context("marketplace_credential")
    }

    assert billing == {"privacy", "offer", "refund_policy"}
    assert marketplace == {"privacy", "credential_policy"}


def test_valid_payload_requires_current_version_and_hash():
    documents = validate_consent_payload(_payload_for("billing"), context="billing")
    assert {document.code for document in documents} == {
        "privacy",
        "offer",
        "refund_policy",
    }


def test_missing_required_consent_is_rejected():
    payload = _payload_for("registration")
    payload = [item for item in payload if item["code"] != "privacy"]

    with pytest.raises(LegalConsentError) as exc:
        validate_consent_payload(payload, context="registration")

    assert exc.value.code == "LEGAL_CONSENT_REQUIRED"


def test_outdated_version_is_rejected():
    payload = _payload_for("registration")
    payload[0]["version"] = "0.0-old"

    with pytest.raises(LegalConsentError) as exc:
        validate_consent_payload(payload, context="registration")

    assert exc.value.code == "LEGAL_DOCUMENT_OUTDATED"


def test_tampered_document_hash_is_rejected():
    payload = _payload_for("marketplace_credential")
    payload[0]["sha256"] = "0" * 64

    with pytest.raises(LegalConsentError) as exc:
        validate_consent_payload(payload, context="marketplace_credential")

    assert exc.value.code == "LEGAL_DOCUMENT_MISMATCH"


def test_public_document_marks_unapproved_text_as_draft():
    document = get_document("terms")
    assert document is not None
    payload = document.public_payload(include_content=True)
    assert payload["status"] == "draft"
    assert payload["legal_review_required"] is True
    assert payload["sha256"] == document.sha256
    assert "СТАТУС: ЧЕРНОВИК" in payload["content"]
