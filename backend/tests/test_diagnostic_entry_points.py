from pathlib import Path


def _frontend_file(*parts: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / Path(*parts)).read_text(encoding="utf-8")


def test_payment_journal_exposes_direct_diagnostics_link():
    payments = _frontend_file("pages", "ControlPanel", "Payments", "index.vue")

    assert "payment_query: payment.id" in payments
    assert "payment_query: paymentDetail.id" in payments
    assert "Открыть в диагностике" in payments


def test_user_and_tariff_cards_keep_contextual_diagnostics_links():
    main = _frontend_file("pages", "ControlPanel", "Main", "index.vue")

    assert "Диагностика пользователя" in main
    assert "user_query: String(route.params.id)" in main
    assert "Диагностика тарифа" in main
    assert "tariff_query: String(route.params.id)" in main


def test_diagnostics_url_contract_uses_entity_filters_instead_of_secrets():
    payments = _frontend_file("pages", "ControlPanel", "Payments", "index.vue")
    main = _frontend_file("pages", "ControlPanel", "Main", "index.vue")

    combined = payments + main
    assert "payment_query" in combined
    assert "user_query" in combined
    assert "tariff_query" in combined
    assert "encrypted_token" not in combined
    assert "Authorization" not in combined
    assert "cvv" not in combined.lower()
