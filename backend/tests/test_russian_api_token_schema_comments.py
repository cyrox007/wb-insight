from pathlib import Path

from models.tokens_model import APIToken


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_api_token_schema_comments_are_russian():
    comments = {
        column.name: column.comment
        for column in APIToken.__table__.columns
        if column.comment
    }

    assert comments == {
        "user_id": "Владелец реквизитов кабинета маркетплейса",
        "marketplace": "Провайдер маркетплейса",
        "token_type": "Тип реквизитов или авторизации конкретного маркетплейса",
        "external_account_id": (
            "Идентификатор продавца или кабинета на стороне маркетплейса; "
            "не является секретом"
        ),
        "encrypted_token": "Зашифрованный секрет маркетплейса",
    }


def test_api_token_model_does_not_restore_known_english_text():
    source = (BACKEND_ROOT / "models/tokens_model.py").read_text(encoding="utf-8")

    forbidden = (
        "Documented Wildberries JWT account types",
        "Encrypted marketplace account credential",
        "Owner of the marketplace account credential",
        "Marketplace provider",
        "Marketplace-specific credential/auth type",
        "Marketplace-side seller/account identifier",
        "Encrypted marketplace secret",
        "Some providers (WB JWT) publish an expiry",
    )

    for phrase in forbidden:
        assert phrase not in source, (
            f"В модели реквизитов снова появился англоязычный текст: {phrase}"
        )
