#!/usr/bin/env python3
"""Релизная приёмка WB Insight без привязки к конкретному почтовому провайдеру.

Основные проверки жизненного цикла вынесены в `release_smoke_core`. Этот входной
модуль отвечает за актуальную политику release gate: почтовый транспорт оценивается
по заявленным возможностям и фактической готовности, а не по имени поставщика.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID

import release_smoke_core as core


SmokeFailure = core.SmokeFailure
SmokeClient = core.SmokeClient


def _normalize_expected_provider(value: str | None) -> str | None:
    """Нормализует необязательный код провайдера без жёсткого allowlist."""
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    if len(normalized) > 64:
        raise SmokeFailure("Код ожидаемого почтового провайдера слишком длинный")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789._-")
    if normalized[0] not in set("abcdefghijklmnopqrstuvwxyz0123456789"):
        raise SmokeFailure("Код ожидаемого почтового провайдера имеет неверный формат")
    if any(char not in allowed for char in normalized):
        raise SmokeFailure("Код ожидаемого почтового провайдера имеет неверный формат")
    return normalized


def _validate_mail_gateway_payload(
    payload: dict,
    *,
    expected_provider: str | None,
    require_email_verification: bool,
    require_password_reset: bool,
) -> None:
    if payload.get("status") != "success":
        raise SmokeFailure("Предварительная проверка почтового шлюза вернула неверный API-конверт")

    gateway = payload.get("gateway") or {}
    provider = str(gateway.get("provider") or "").strip().lower()
    if not provider:
        raise SmokeFailure("Почтовый шлюз не сообщил фактический провайдер")
    if expected_provider and provider != expected_provider:
        raise SmokeFailure(
            "Почтовый провайдер не совпадает с ожидаемым: "
            f"ожидался {expected_provider}, получен {provider}"
        )
    if gateway.get("ready") is not True:
        diagnostic = str(gateway.get("diagnostic_code") or "not_ready")
        raise SmokeFailure(f"Почтовый шлюз не готов ({diagnostic})")

    capabilities = gateway.get("capabilities")
    if not isinstance(capabilities, dict):
        raise SmokeFailure("Почтовый шлюз не сообщил реестр возможностей адаптера")
    if capabilities.get("transactional") is not True:
        raise SmokeFailure("Почтовый адаптер не поддерживает транзакционные письма")

    system_mail = gateway.get("system_mail") or {}
    if require_email_verification:
        verification = system_mail.get("email_verification") or {}
        if verification.get("ready") is not True:
            raise SmokeFailure("Отправка подтверждения email не готова")
    if require_password_reset:
        recovery = system_mail.get("password_reset") or {}
        if recovery.get("ready") is not True:
            raise SmokeFailure("Отправка восстановления пароля не готова")


def run_mail_gateway_readiness_smoke(
    client: SmokeClient,
    *,
    expected_provider: str | None,
    require_email_verification: bool,
    require_password_reset: bool,
) -> dict:
    """Проверяет mail gateway по возможностям адаптера до реальной отправки."""
    payload = client.request(
        "GET",
        "/control-panel/mail/gateway",
        auth=True,
    )
    _validate_mail_gateway_payload(
        payload,
        expected_provider=expected_provider,
        require_email_verification=require_email_verification,
        require_password_reset=require_password_reset,
    )
    gateway = payload.get("gateway") or {}
    provider = str(gateway.get("provider") or "unknown").strip().lower()
    capabilities = gateway.get("capabilities") or {}
    system_mail = gateway.get("system_mail") or {}
    evidence = {
        "provider": provider,
        "expected_provider": expected_provider,
        "source": str(gateway.get("source") or "unknown"),
        "config_source": str(gateway.get("config_source") or "unknown"),
        "transport_kind": str(
            gateway.get("transport_kind")
            or capabilities.get("transport_kind")
            or "unknown"
        ),
        "transactional": bool(capabilities.get("transactional")),
        "marketing": bool(capabilities.get("marketing")),
        "one_click_unsubscribe": bool(capabilities.get("one_click_unsubscribe")),
        "email_verification_ready": bool(
            (system_mail.get("email_verification") or {}).get("ready")
        ),
        "password_reset_ready": bool(
            (system_mail.get("password_reset") or {}).get("ready")
        ),
    }
    print(f"[ok] готовность почтового шлюза: provider={provider}")
    return evidence


def run_mail_gateway_authenticated_preflight(
    base_url: str,
    *,
    email: str,
    password: str,
    expected_provider: str | None,
    require_email_verification: bool,
    require_password_reset: bool,
) -> dict:
    """Проверяет почтовый шлюз под staff-сессией и затем отзывает её."""
    client = SmokeClient(base_url)
    preflight_error: SmokeFailure | None = None
    evidence: dict | None = None
    try:
        core._login_smoke_client(client, email, password)
        evidence = run_mail_gateway_readiness_smoke(
            client,
            expected_provider=expected_provider,
            require_email_verification=require_email_verification,
            require_password_reset=require_password_reset,
        )
    except SmokeFailure as exc:
        preflight_error = exc
    finally:
        if client.access_token or any(True for _ in client.cookies):
            try:
                core.run_logout_smoke(client)
            except SmokeFailure as cleanup_exc:
                if preflight_error is not None:
                    raise SmokeFailure(
                        f"{preflight_error}; завершение preflight-сессии также завершилось ошибкой"
                    ) from cleanup_exc
                raise

    if preflight_error is not None:
        raise preflight_error
    if evidence is None:
        raise SmokeFailure("Предварительная проверка почтового шлюза завершилась без evidence")
    return evidence


def _validate_beta_gate_args(args: argparse.Namespace) -> None:
    """Проверяет обязательные входы beta gate до сетевых запросов."""
    if args.public_only:
        raise SmokeFailure("Beta gate нельзя запускать в режиме public-only")
    if args.skip_disposable_registration:
        raise SmokeFailure("Beta gate требует полный жизненный цикл тестовой регистрации")
    if not args.evidence_output:
        raise SmokeFailure("Beta gate требует --evidence-output/SMOKE_EVIDENCE_OUTPUT")
    if not core._is_beta_version(args.expected_version):
        raise SmokeFailure("Beta gate требует VERSION с суффиксом -beta.N")
    origin = core._safe_base_origin(str(args.base_url or ""))
    if urlparse(origin).scheme != "https":
        raise SmokeFailure("Beta gate требует публичный HTTPS origin")
    if not args.email or not args.password:
        raise SmokeFailure("Beta gate требует SMOKE_EMAIL и SMOKE_PASSWORD")
    if not args.require_email_verification:
        raise SmokeFailure("Beta gate требует реальное подтверждение email")
    if not args.require_password_reset:
        raise SmokeFailure("Beta gate требует реальное восстановление пароля")
    if not args.mail_gateway_smoke:
        raise SmokeFailure("Beta gate требует проверку готовности почтового шлюза")
    if not args.audit_smoke:
        raise SmokeFailure("Beta gate требует проверку устойчивого audit correlation")
    if not str(args.wb_token or "").strip():
        raise SmokeFailure("Beta gate требует реальный SMOKE_WB_TOKEN")

    disposable = core._disposable_email(
        args.disposable_email_template,
        UUID("12345678-1234-5678-1234-567812345678"),
    )
    core._require_real_disposable_mail(
        disposable,
        mail_token_command=args.mail_token_command,
    )


def _self_test() -> None:
    """Закрепляет provider-neutral контракт поверх базовых smoke-проверок."""
    core._self_test()

    payload = {
        "status": "success",
        "gateway": {
            "provider": "resend",
            "ready": True,
            "source": "database",
            "config_source": "auto",
            "transport_kind": "https_api",
            "capabilities": {
                "transport_kind": "https_api",
                "transactional": True,
                "marketing": True,
                "one_click_unsubscribe": True,
            },
            "system_mail": {
                "email_verification": {"ready": True},
                "password_reset": {"ready": True},
            },
        },
    }
    _validate_mail_gateway_payload(
        payload,
        expected_provider="resend",
        require_email_verification=True,
        require_password_reset=True,
    )

    class _FakeGatewayClient:
        def request(self, method, path, *, auth=False, **_kwargs):
            assert method == "GET"
            assert path == "/control-panel/mail/gateway"
            assert auth is True
            return payload

    evidence = run_mail_gateway_readiness_smoke(
        _FakeGatewayClient(),  # type: ignore[arg-type]
        expected_provider="resend",
        require_email_verification=True,
        require_password_reset=True,
    )
    assert evidence["provider"] == "resend"
    assert evidence["transactional"] is True
    assert evidence["transport_kind"] == "https_api"

    beta_args = argparse.Namespace(
        base_url="https://staging.example.com",
        email="staff@example.com",
        password="secret",
        expected_version="0.9.0-beta.1",
        public_only=False,
        skip_disposable_registration=False,
        disposable_email_template="release-smoke+{uuid}@qa.example.com",
        mail_token_command="python3 ops/imap_mail_token_hook.py",
        require_email_verification=True,
        require_password_reset=True,
        mail_gateway_smoke=True,
        expected_mail_provider="resend",
        audit_smoke=True,
        wb_token="secret-wb-token",
        evidence_output=Path("/tmp/release-smoke.json"),
    )
    _validate_beta_gate_args(beta_args)

    smtp_args = argparse.Namespace(**vars(beta_args))
    smtp_args.expected_mail_provider = "smtp"
    _validate_beta_gate_args(smtp_args)

    assert _normalize_expected_provider(" Resend ") == "resend"
    try:
        _normalize_expected_provider("bad provider!")
    except SmokeFailure:
        pass
    else:
        raise AssertionError("Некорректный код провайдера неожиданно прошёл проверку")

    print("[ok] provider-neutral release smoke self-test")


def main() -> int:
    args = core.parse_args()
    if args.self_test:
        _self_test()
        return 0
    if not args.base_url:
        raise SmokeFailure("Требуется SMOKE_BASE_URL или --base-url")
    core._safe_base_origin(args.base_url)
    if args.mail_token_timeout <= 0 or args.mail_token_timeout > 1800:
        raise SmokeFailure("Таймаут получения почтового токена должен быть от 1 до 1800 секунд")
    if args.skip_disposable_registration and (
        args.require_email_verification or args.require_password_reset
    ):
        raise SmokeFailure(
            "Обязательные email verification/password reset нельзя сочетать с пропуском тестовой регистрации"
        )

    args.expected_mail_provider = _normalize_expected_provider(args.expected_mail_provider)

    if args.evidence_output:
        commit = str(args.commit or "").strip().lower()
        if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
            raise SmokeFailure(
                "Структурированное evidence требует полный Git SHA через --commit/RELEASE_SHA"
            )
        args.commit = commit
        environment = str(args.environment or "").strip()
        if not environment:
            raise SmokeFailure(
                "Структурированное evidence требует --environment/ACCEPTANCE_ENVIRONMENT"
            )
        args.environment = environment

    if args.beta_gate:
        _validate_beta_gate_args(args)

    checks: dict[str, bool] = {
        "public_health_legal": False,
        "disposable_registration": False,
        "email_verification": False,
        "password_reset": False,
        "password_reset_throttle": False,
        "password_reset_session_revoked": False,
        "demo_activation": False,
        "legal_consent_evidence": False,
        "disposable_refresh_restore": False,
        "deactivation": False,
        "inactive_login_rejected": False,
        "authenticated_profile": False,
        "authenticated_refresh_restore": False,
        "dashboard_contract": False,
        "mail_gateway_ready": False,
        "audit_correlation": False,
        "wb_credential": False,
        "billing_init": False,
        "logout_session_revoke": False,
    }

    mail_gateway_evidence: dict | None = None
    client = SmokeClient(args.base_url)
    core.run_public_smoke(client, args.expected_version)
    checks["public_health_legal"] = True

    if args.public_only:
        if args.evidence_output:
            core._write_evidence(
                args.evidence_output,
                args=args,
                checks=checks,
                mail_gateway=mail_gateway_evidence,
            )
        return 0

    if not args.email or not args.password:
        raise SmokeFailure("Для authenticated smoke требуются SMOKE_EMAIL и SMOKE_PASSWORD")

    if args.mail_gateway_smoke:
        mail_gateway_evidence = run_mail_gateway_authenticated_preflight(
            args.base_url,
            email=args.email,
            password=args.password,
            expected_provider=args.expected_mail_provider,
            require_email_verification=args.require_email_verification,
            require_password_reset=args.require_password_reset,
        )
        checks["mail_gateway_ready"] = True

    if not args.skip_disposable_registration:
        disposable = core.run_disposable_registration_smoke(
            args.base_url,
            email_template=args.disposable_email_template,
            mail_token_command=args.mail_token_command,
            mail_token_timeout=args.mail_token_timeout,
            require_email_verification=args.require_email_verification,
            require_password_reset=args.require_password_reset,
            mail_admin_email=args.email,
            mail_admin_password=args.password,
        )
        checks.update(disposable)
        checks["disposable_refresh_restore"] = disposable["refresh_restore"]
        checks.pop("refresh_restore", None)

    authenticated_error: SmokeFailure | None = None
    try:
        core.run_authenticated_smoke(client, args.email, args.password)
        checks["authenticated_profile"] = True
        checks["authenticated_refresh_restore"] = True
        checks["dashboard_contract"] = True
        if args.audit_smoke:
            core.run_audit_correlation_smoke(client)
            checks["audit_correlation"] = True
        if args.wb_token:
            core.run_wb_credential_smoke(client, args.wb_token)
            checks["wb_credential"] = True
        if args.billing_tariff:
            core.run_billing_init_smoke(client, args.billing_tariff)
            checks["billing_init"] = True
    except SmokeFailure as exc:
        authenticated_error = exc
    finally:
        if client.access_token or any(True for _ in client.cookies):
            try:
                core.run_logout_smoke(client)
                checks["logout_session_revoke"] = True
            except SmokeFailure as cleanup_exc:
                if authenticated_error is not None:
                    raise SmokeFailure(
                        f"{authenticated_error}; завершение authenticated smoke также завершилось ошибкой"
                    ) from cleanup_exc
                raise

    if authenticated_error is not None:
        raise authenticated_error

    if args.evidence_output:
        core._write_evidence(
            args.evidence_output,
            args=args,
            checks=checks,
            mail_gateway=mail_gateway_evidence,
        )
        print(f"[ok] структурированное release smoke evidence: {args.evidence_output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeFailure as exc:
        print(f"[failed] {exc}", file=sys.stderr)
        raise SystemExit(1)
