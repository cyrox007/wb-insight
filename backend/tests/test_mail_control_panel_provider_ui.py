from pathlib import Path


MAIL_PAGE = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "src"
    / "pages"
    / "ControlPanel"
    / "Mail"
    / "index.vue"
)


def _mail_page_source() -> str:
    return MAIL_PAGE.read_text(encoding="utf-8")


def test_mail_gateway_ui_uses_provider_capabilities_for_optional_features():
    source = _mail_page_source()

    required = (
        "selectedProviderSupportsMarketing",
        "selectedProviderSupportsReplyTo",
        "selectedProviderRequiresKeyId",
        'v-if="selectedProviderSupportsMarketing"',
        'v-if="selectedProviderSupportsReplyTo"',
        'v-if="selectedProviderRequiresKeyId"',
    )
    for marker in required:
        assert marker in source


def test_mail_gateway_ui_does_not_disable_https_marketing_by_transport_type():
    source = _mail_page_source()

    forbidden = (
        "selectedProviderUsesHttpsApi.value ? false : gatewayForm.enabled",
        "selectedProviderUsesHttpsApi.value ? '' : gatewayForm.reply_to_email",
        "provider === 'rusender'",
        'provider === "rusender"',
        "provider === 'resend'",
        'provider === "resend"',
    )
    for marker in forbidden:
        assert marker not in source


def test_mail_gateway_ui_sends_key_id_only_when_provider_requires_it():
    source = _mail_page_source()

    assert (
        "if (selectedProviderRequiresKeyId.value) payload.key_id = gatewayForm.key_id"
        in source
    )
    assert (
        "enabled: selectedProviderSupportsMarketing.value ? gatewayForm.enabled : false"
        in source
    )
    assert (
        "reply_to_email: selectedProviderSupportsReplyTo.value ? "
        "gatewayForm.reply_to_email : ''"
        in source
    )
