import os
from urllib.parse import urlparse


_RESERVED_EXAMPLE_DOMAINS = ("example.com", "example.org", "example.net")
_WEAK_SECRET_VALUES = {"admin", "changeme", "change-me", "password", "secret"}
_MAIL_PROVIDERS = {"smtp", "rusender", "resend"}
_MARKETING_MAIL_PROVIDERS = {"smtp", "resend"}


def _is_reserved_example_host(hostname: str | None) -> bool:
    if not hostname:
        return True
    host = hostname.rstrip(".").lower()
    return any(
        host == domain or host.endswith(f".{domain}")
        for domain in _RESERVED_EXAMPLE_DOMAINS
    )


def _is_placeholder(value: str | None) -> bool:
    normalized = (value or "").strip().lower()
    return (
        not normalized
        or "replace-with-" in normalized
        or normalized in _WEAK_SECRET_VALUES
    )


class LifecycleConfig:
    PASSWORD_RESET_ENABLED = os.getenv("PASSWORD_RESET_ENABLED", "false").lower() == "true"
    PASSWORD_RESET_BASE_URL = os.getenv("PASSWORD_RESET_BASE_URL", "").strip()
    PASSWORD_RESET_TOKEN_TTL_MINUTES = int(
        os.getenv("PASSWORD_RESET_TOKEN_TTL_MINUTES", "30")
    )
    PASSWORD_RESET_RESEND_SECONDS = int(
        os.getenv("PASSWORD_RESET_RESEND_SECONDS", "60")
    )

    EMAIL_VERIFICATION_ENABLED = os.getenv("EMAIL_VERIFICATION_ENABLED", "false").lower() == "true"
    EMAIL_VERIFICATION_BASE_URL = os.getenv("EMAIL_VERIFICATION_BASE_URL", "").strip()
    EMAIL_VERIFICATION_TOKEN_TTL_MINUTES = int(
        os.getenv("EMAIL_VERIFICATION_TOKEN_TTL_MINUTES", "60")
    )
    EMAIL_VERIFICATION_RESEND_SECONDS = int(
        os.getenv("EMAIL_VERIFICATION_RESEND_SECONDS", "60")
    )

    MAIL_DELIVERY_ENABLED = os.getenv("MAIL_DELIVERY_ENABLED", "false").lower() == "true"
    MAIL_PROVIDER = os.getenv("MAIL_PROVIDER", "smtp").strip().lower() or "smtp"
    MAIL_CONFIG_SOURCE = os.getenv("MAIL_CONFIG_SOURCE", "auto").strip().lower() or "auto"
    MAIL_BATCH_SIZE = int(os.getenv("MAIL_BATCH_SIZE", "25"))
    MAIL_MAX_ATTEMPTS = int(os.getenv("MAIL_MAX_ATTEMPTS", "5"))
    MAIL_RETRY_BASE_SECONDS = int(os.getenv("MAIL_RETRY_BASE_SECONDS", "30"))
    MAIL_UNSUBSCRIBE_BASE_URL = os.getenv("MAIL_UNSUBSCRIBE_BASE_URL", "").strip()
    MAIL_UNSUBSCRIBE_HMAC_KEY = os.getenv("MAIL_UNSUBSCRIBE_HMAC_KEY", "").strip()

    SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip() or None
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD") or None
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "").strip()
    SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "WB Insight").strip() or "WB Insight"
    SMTP_REPLY_TO_EMAIL = os.getenv("SMTP_REPLY_TO_EMAIL", "").strip() or None
    SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "true").lower() == "true"
    SMTP_TIMEOUT_SECONDS = float(os.getenv("SMTP_TIMEOUT_SECONDS", "10"))

    RUSENDER_API_BASE_URL = os.getenv(
        "RUSENDER_API_BASE_URL",
        "https://api.rusender.ru",
    ).strip().rstrip("/")
    RUSENDER_KEY_ID = os.getenv("RUSENDER_KEY_ID", "").strip()
    RUSENDER_API_TOKEN = os.getenv("RUSENDER_API_TOKEN", "").strip() or None
    RUSENDER_TIMEOUT_SECONDS = float(os.getenv("RUSENDER_TIMEOUT_SECONDS", "10"))

    RESEND_API_BASE_URL = os.getenv(
        "RESEND_API_BASE_URL",
        "https://api.resend.com",
    ).strip().rstrip("/")
    RESEND_API_TOKEN = os.getenv("RESEND_API_TOKEN", "").strip() or None
    RESEND_TIMEOUT_SECONDS = float(os.getenv("RESEND_TIMEOUT_SECONDS", "10"))

    ACCOUNT_DEACTIVATION_RETENTION_DAYS = int(
        os.getenv("ACCOUNT_DEACTIVATION_RETENTION_DAYS", "90")
    )

    def _validate_https_url(self, name: str, value: str, *, production: bool) -> None:
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.hostname:
            raise RuntimeError(f"{name} должен содержать абсолютный URL")
        if not production:
            return
        if parsed.scheme.lower() != "https":
            raise RuntimeError(f"В production {name} должен использовать https://")
        hostname = parsed.hostname.lower()
        if "replace-with-" in hostname or _is_reserved_example_host(hostname):
            raise RuntimeError(f"В production {name} должен указывать на реальный сервис")

    def _validate_sender_domain(self, *, production: bool) -> None:
        if not self.SMTP_FROM_EMAIL or "@" not in self.SMTP_FROM_EMAIL:
            raise RuntimeError("Для почтовой доставки нужен корректный SMTP_FROM_EMAIL")
        if not production:
            return
        from_domain = self.SMTP_FROM_EMAIL.rpartition("@")[2].strip().lower()
        if not from_domain or _is_reserved_example_host(from_domain):
            raise RuntimeError(
                "В production SMTP_FROM_EMAIL должен использовать реальный домен отправителя"
            )

    def _validate_smtp_transport(self, *, production: bool) -> None:
        missing = [
            name
            for name, value in {
                "SMTP_HOST": self.SMTP_HOST,
                "SMTP_FROM_EMAIL": self.SMTP_FROM_EMAIL,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Для SMTP-доставки нужны параметры: " + ", ".join(missing)
            )
        if bool(self.SMTP_USERNAME) != bool(self.SMTP_PASSWORD):
            raise RuntimeError("SMTP_USERNAME и SMTP_PASSWORD должны быть настроены вместе")
        self._validate_sender_domain(production=production)
        if not production:
            return
        if not self.SMTP_STARTTLS:
            raise RuntimeError("В production SMTP должен использовать STARTTLS")
        smtp_host = self.SMTP_HOST.rstrip(".").lower()
        if "replace-with-" in smtp_host or _is_reserved_example_host(smtp_host):
            raise RuntimeError("В production SMTP_HOST должен указывать на реальный сервер")
        if self.SMTP_USERNAME and _is_placeholder(self.SMTP_USERNAME):
            raise RuntimeError("В production SMTP_USERNAME должен быть заменён реальным значением")
        if self.SMTP_PASSWORD and _is_placeholder(self.SMTP_PASSWORD):
            raise RuntimeError("В production SMTP_PASSWORD должен быть заменён реальным секретом")

    def _validate_rusender_transport(self, *, production: bool) -> None:
        missing = [
            name
            for name, value in {
                "RUSENDER_API_BASE_URL": self.RUSENDER_API_BASE_URL,
                "RUSENDER_KEY_ID": self.RUSENDER_KEY_ID,
                "RUSENDER_API_TOKEN": self.RUSENDER_API_TOKEN,
                "SMTP_FROM_EMAIL": self.SMTP_FROM_EMAIL,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Для RuSender нужны параметры: " + ", ".join(missing)
            )
        if not self.RUSENDER_KEY_ID.isdigit():
            raise RuntimeError("RUSENDER_KEY_ID должен быть числом")
        if self.RUSENDER_TIMEOUT_SECONDS <= 0:
            raise RuntimeError("RUSENDER_TIMEOUT_SECONDS должен быть больше нуля")
        self._validate_https_url(
            "RUSENDER_API_BASE_URL",
            self.RUSENDER_API_BASE_URL,
            production=production,
        )
        self._validate_sender_domain(production=production)
        if production and _is_placeholder(self.RUSENDER_API_TOKEN):
            raise RuntimeError(
                "В production RUSENDER_API_TOKEN должен быть заменён реальным секретом"
            )

    def _validate_resend_transport(self, *, production: bool) -> None:
        missing = [
            name
            for name, value in {
                "RESEND_API_BASE_URL": self.RESEND_API_BASE_URL,
                "RESEND_API_TOKEN": self.RESEND_API_TOKEN,
                "SMTP_FROM_EMAIL": self.SMTP_FROM_EMAIL,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Для Resend нужны параметры: " + ", ".join(missing)
            )
        if self.RESEND_TIMEOUT_SECONDS <= 0:
            raise RuntimeError("RESEND_TIMEOUT_SECONDS должен быть больше нуля")
        self._validate_https_url(
            "RESEND_API_BASE_URL",
            self.RESEND_API_BASE_URL,
            production=production,
        )
        self._validate_sender_domain(production=production)
        if production and _is_placeholder(self.RESEND_API_TOKEN):
            raise RuntimeError(
                "В production RESEND_API_TOKEN должен быть заменён реальным секретом"
            )

    def _validate_mail_transport(self, *, production: bool) -> None:
        if self.MAIL_PROVIDER not in _MAIL_PROVIDERS:
            supported = ", ".join(sorted(_MAIL_PROVIDERS))
            raise RuntimeError(
                f"Неподдерживаемый MAIL_PROVIDER: {self.MAIL_PROVIDER}. Доступны: {supported}"
            )
        if self.MAIL_PROVIDER == "smtp":
            self._validate_smtp_transport(production=production)
            return
        if self.MAIL_PROVIDER == "rusender":
            self._validate_rusender_transport(production=production)
            return
        self._validate_resend_transport(production=production)

    def validate(self, *, production: bool) -> None:
        if self.PASSWORD_RESET_TOKEN_TTL_MINUTES <= 0:
            raise RuntimeError("PASSWORD_RESET_TOKEN_TTL_MINUTES должен быть больше нуля")
        if self.PASSWORD_RESET_RESEND_SECONDS <= 0:
            raise RuntimeError("PASSWORD_RESET_RESEND_SECONDS должен быть больше нуля")
        if self.EMAIL_VERIFICATION_TOKEN_TTL_MINUTES <= 0:
            raise RuntimeError("EMAIL_VERIFICATION_TOKEN_TTL_MINUTES должен быть больше нуля")
        if self.EMAIL_VERIFICATION_RESEND_SECONDS <= 0:
            raise RuntimeError("EMAIL_VERIFICATION_RESEND_SECONDS должен быть больше нуля")
        if len(self.SMTP_FROM_NAME) > 160:
            raise RuntimeError("SMTP_FROM_NAME не должен превышать 160 символов")
        if self.SMTP_REPLY_TO_EMAIL and (
            "@" not in self.SMTP_REPLY_TO_EMAIL or len(self.SMTP_REPLY_TO_EMAIL) > 320
        ):
            raise RuntimeError("SMTP_REPLY_TO_EMAIL должен содержать корректный email")
        if (
            self.MAIL_BATCH_SIZE <= 0
            or self.MAIL_MAX_ATTEMPTS <= 0
            or self.MAIL_RETRY_BASE_SECONDS <= 0
        ):
            raise RuntimeError("Параметры почтовой очереди должны быть больше нуля")
        if self.SMTP_PORT <= 0 or self.SMTP_TIMEOUT_SECONDS <= 0:
            raise RuntimeError("SMTP port и timeout должны быть больше нуля")
        if self.RUSENDER_TIMEOUT_SECONDS <= 0:
            raise RuntimeError("RUSENDER_TIMEOUT_SECONDS должен быть больше нуля")
        if self.RESEND_TIMEOUT_SECONDS <= 0:
            raise RuntimeError("RESEND_TIMEOUT_SECONDS должен быть больше нуля")
        if self.ACCOUNT_DEACTIVATION_RETENTION_DAYS <= 0:
            raise RuntimeError("ACCOUNT_DEACTIVATION_RETENTION_DAYS должен быть больше нуля")

        if self.MAIL_CONFIG_SOURCE not in {"auto", "environment", "database"}:
            raise RuntimeError(
                "MAIL_CONFIG_SOURCE должен быть auto, environment или database"
            )

        if (
            self.MAIL_CONFIG_SOURCE == "environment"
            and self.MAIL_DELIVERY_ENABLED
            and self.MAIL_PROVIDER not in _MARKETING_MAIL_PROVIDERS
        ):
            raise RuntimeError(
                "Выбранный почтовый адаптер не поддерживает маркетинговые кампании; установите MAIL_DELIVERY_ENABLED=false"
            )

        needs_mail = (
            self.PASSWORD_RESET_ENABLED
            or self.EMAIL_VERIFICATION_ENABLED
            or self.MAIL_DELIVERY_ENABLED
        )
        if needs_mail and self.MAIL_CONFIG_SOURCE == "environment":
            self._validate_mail_transport(production=production)
        elif needs_mail and self.MAIL_CONFIG_SOURCE == "auto":
            # В auto-конфигурации действующий транспорт может храниться в базе.
            # Проверка ENV выполняется позднее только при отсутствии DB-настройки.
            pass

        if self.PASSWORD_RESET_ENABLED:
            if not self.PASSWORD_RESET_BASE_URL:
                raise RuntimeError(
                    "PASSWORD_RESET_ENABLED требует PASSWORD_RESET_BASE_URL"
                )
            self._validate_https_url(
                "PASSWORD_RESET_BASE_URL",
                self.PASSWORD_RESET_BASE_URL,
                production=production,
            )

        if self.MAIL_DELIVERY_ENABLED and production:
            if not self.MAIL_UNSUBSCRIBE_BASE_URL:
                raise RuntimeError(
                    "Маркетинговая почта в production требует MAIL_UNSUBSCRIBE_BASE_URL"
                )
            self._validate_https_url(
                "MAIL_UNSUBSCRIBE_BASE_URL",
                self.MAIL_UNSUBSCRIBE_BASE_URL,
                production=True,
            )
            if (
                len(self.MAIL_UNSUBSCRIBE_HMAC_KEY) < 32
                or _is_placeholder(self.MAIL_UNSUBSCRIBE_HMAC_KEY)
            ):
                raise RuntimeError(
                    "Маркетинговая почта в production требует стойкий MAIL_UNSUBSCRIBE_HMAC_KEY"
                )

        if self.EMAIL_VERIFICATION_ENABLED:
            if not self.EMAIL_VERIFICATION_BASE_URL:
                raise RuntimeError(
                    "EMAIL_VERIFICATION_ENABLED требует EMAIL_VERIFICATION_BASE_URL"
                )
            self._validate_https_url(
                "EMAIL_VERIFICATION_BASE_URL",
                self.EMAIL_VERIFICATION_BASE_URL,
                production=production,
            )


lifecycle_config = LifecycleConfig()
