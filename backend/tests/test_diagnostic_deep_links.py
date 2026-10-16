from pathlib import Path


def _frontend_file(*parts: str) -> str:
    root = Path(__file__).resolve().parents[2]
    return (root / "frontend" / "src" / Path(*parts)).read_text(encoding="utf-8")


def test_diagnostics_hub_reads_filters_from_route_and_syncs_url():
    hub = _frontend_file("pages", "ControlPanel", "Diagnostics", "Hub.vue")

    assert "filtersFromRoute" in hub
    assert "syncFilterRoute" in hub
    assert "route.fullPath" in hub
    assert "control-panel.diagnostics" in hub
    assert "token_query" in hub
    assert "payment_query" in hub
    assert "tariff_query" in hub
    assert "job_query" in hub


def test_filter_panel_can_be_prefilled_programmatically():
    panel = _frontend_file("pages", "ControlPanel", "Diagnostics", "FilterPanel.vue")

    assert "function setFilters" in panel
    assert "defineExpose({ applyMatch, resetFilters, setFilters })" in panel
    assert "created_from" in panel
    assert "attention_only" in panel


def test_control_panel_exposes_contextual_diagnostics_links():
    main = _frontend_file("pages", "ControlPanel", "Main", "index.vue")

    assert "diagnosticsContextLink" in main
    assert "Диагностика пользователя" in main
    assert "user_query" in main
    assert "Диагностика тарифа" in main
    assert "tariff_query" in main


def test_marketplace_credential_has_direct_journal_action():
    hub = _frontend_file("pages", "ControlPanel", "Diagnostics", "Hub.vue")

    assert "Журнал кабинета" in hub
    assert "filterCredential" in hub
    assert "credential.id" in hub
