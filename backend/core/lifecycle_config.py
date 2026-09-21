import os
from urllib.parse import urlparse


_RESERVED_EXAMPLE_DOMAINS = ("example.com", "example.org", "example.net")
_WEAK_SECRET_VALUES = {"admin", "changeme", "change-me", "password", "secret"}


def _is_reserved_example_host(hostname: str | None) -> bool:
    if not hostname:
        return True
    host = hostname.rstrip(".").lower()
    return any(host == domain or host.endswith(f".{domain}") for domain in _RESERVED_EXAMPLE_DOMAINS)


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
    PASSWORD_RESET_TOKEN_TTL_MINUTES = int(os.getenv("PASSWORD_RESET_TOKEN_TTL_MINUTES", "30"))
    PASSWORD_RESET_RESEND_SECONDS = int(os.getenv("PASSWORD_RESET_RESEND_SECONDS", "60"))

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

    ACCOUNT_DEACTIVATION_RETENTION_DAYS = int(
        os.getenv("ACCOUNT_DEACTIVATION_RETENTION_DAYS", "90")
    )

    def _validate_https_url(self, name: str, value: str, *, production: bool) -> None:
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.hostname:
            raise RuntimeError(f"{name} must be an absolute URL")
        if production:
            if parsed.scheme.lower() != "https":
                raise RuntimeError(f"Production {name} must use https://")
            hostname = parsed.hostname.lower()
            if "replace-with-" in hostname or _is_reserved_example_host(hostname):
                raise RuntimeError(f"Production {name} must use the real service host")

    def _validate_mail_transport(self, *, production: bool) -> None:
        if self.MAIL_PROVIDER not in {"smtp", "rusender"}:
            raise RuntimeError(f"Unsupported MAIL_PROVIDER: {self.MAIL_PROVIDER}")

        if self.MAIL_PROVIDER == "smtp":
            missing = [
                name
                for name, value in {
                    "SMTP_HOST": self.SMTP_HOST,
                    "SMTP_FROM_EMAIL": self.SMTP_FROM_EMAIL,
                }.items()
                if not value
            ]
            if missing:
                raise RuntimeError("Mail delivery requires: " + ", ".join(missing))
            if bool(self.SMTP_USERNAME) != bool(self.SMTP_PASSWORD):
                raise RuntimeError("SMTP_USERNAME and SMTP_PASSWORD must be configured together")
            if not production:
                return
            if not self.SMTP_STARTTLS:
                raise RuntimeError("Production mail delivery requires SMTP_STARTTLS=true")
            smtp_host = self.SMTP_HOST.rstrip(".").lower()
            if "replace-with-" in smtp_host or _is_reserved_example_host(smtp_host):
                raise RuntimeError("Production SMTP_HOST must use the real provider host")
            from_domain = self.SMTP_FROM_EMAIL.rpartition("@")[2].strip().lower()
            if not from_domain or _is_reserved_example_host(from_domain):
                raise RuntimeError("Production SMTP_FROM_EMAIL must use the real sender domain")
            if self.SMTP_USERNAME and _is_placeholder(self.SMTP_USERNAME):
                raise RuntimeError("Production SMTP_USERNAME must be replaced with a provider value")
            if self.SMTP_PASSWORD and _is_placeholder(self.SMTP_PASSWORD):
                raise RuntimeError("Production SMTP_PASSWORD must be replaced with a provider secret")
            return

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
            raise RuntimeError("RuSender delivery requires: " + ", ".join(missing))
        if not self.RUSENDER_KEY_ID.isdigit():
            raise RuntimeError("RUSENDER_KEY_ID must be numeric")
        if self.RUSENDER_TIMEOUT_SECONDS <= 0:
            raise RuntimeError("RUSENDER_TIMEOUT_SECONDS must be positive")
        self._validate_https_url(
            "RUSENDER_API_BASE_URL",
            self.RUSENDER_API_BASE_URL,
            production=production,
        )
        if production:
            from_domain = self.SMTP_FROM_EMAIL.rpartition("@")[2].strip().lower()
            if not from_domain or _is_reserved_example_host(from_domain):
                raise RuntimeError("Production SMTP_FROM_EMAIL must use the real sender domain")
            if _is_placeholder(self.RUSENDER_API_TOKEN):
                raise RuntimeError("Production RUSENDER_API_TOKEN must be replaced with a provider secret")

    def validate(self, *, production: bool) -> None:
        if self.PASSWORD_RESET_TOKEN_TTL_MINUTES <= 0:
            raise RuntimeError("PASSWORD_RESET_TOKEN_TTL_MINUTES must be positive")
        if self.PASSWORD_RESET_RESEND_SECONDS <= 0:
            raise RuntimeError("PASSWORD_RESET_RESEND_SECONDS must be positive")
        if self.EMAIL_VERIFICATION_TOKEN_TTL_MINUTES <= 0:
            raise RuntimeError("EMAIL_VERIFICATION_TOKEN_TTL_MINUTES must be positive")
        if self.EMAIL_VERIFICATION_RESEND_SECONDS <= 0:
            raise RuntimeError("EMAIL_VERIFICATION_RESEND_SECONDS must be positive")
        if len(self.SMTP_FROM_NAME) > 160:
            raise RuntimeError("SMTP_FROM_NAME must be at most 160 characters")
        if self.SMTP_REPLY_TO_EMAIL and (
            "@" not in self.SMTP_REPLY_TO_EMAIL or len(self.SMTP_REPLY_TO_EMAIL) > 320
        ):
            raise RuntimeError("SMTP_REPLY_TO_EMAIL must be a valid email address")
        if self.MAIL_BATCH_SIZE <= 0 or self.MAIL_MAX_ATTEMPTS <= 0 or self.MAIL_RETRY_BASE_SECONDS <= 0:
            raise RuntimeError("Mail queue limits must be positive")
        if self.SMTP_PORT <= 0 or self.SMTP_TIMEOUT_SECONDS <= 0:
            raise RuntimeError("SMTP port and timeout must be positive")
        if self.RUSENDER_TIMEOUT_SECONDS <= 0:
            raise RuntimeError("RUSENDER_TIMEOUT_SECONDS must be positive")
        if self.ACCOUNT_DEACTIVATION_RETENTION_DAYS <= 0:
            raise RuntimeError("ACCOUNT_DEACTIVATION_RETENTION_DAYS must be positive")

        if self.MAIL_CONFIG_SOURCE not in {"auto", "environment", "database"}:
            raise RuntimeError("MAIL_CONFIG_SOURCE must be auto, environment or database")

        if self.MAIL_PROVIDER == "rusender" and self.MAIL_DELIVERY_ENABLED:
            raise RuntimeError(
                "RuSender transactional adapter does not support marketing campaigns; set MAIL_DELIVERY_ENABLED=false"
            )

        needs_mail = (
            self.PASSWORD_RESET_ENABLED
            or self.EMAIL_VERIFICATION_ENABLED
            or self.MAIL_DELIVERY_ENABLED
        )
        if needs_mail and self.MAIL_CONFIG_SOURCE == "environment":
            self._validate_mail_transport(production=production)
        elif needs_mail and self.MAIL_CONFIG_SOURCE == "auto":
            # In auto mode the database runtime configuration may be the
            # effective transport. Validate ENV only when an ENV transport is
            # actually present as a fallback.
            env_transport_present = (
                bool(self.SMTP_HOST or self.SMTP_FROM_EMAIL)
                if self.MAIL_PROVIDER == "smtp"
                else bool(self.RUSENDER_KEY_ID or self.RUSENDER_API_TOKEN or self.SMTP_FROM_EMAIL)
            )
            if env_transport_present:
                self._validate_mail_transport(production=production)

        if self.PASSWORD_RESET_ENABLED:
            if not self.PASSWORD_RESET_BASE_URL:
                raise RuntimeError("PASSWORD_RESET_ENABLED requires PASSWORD_RESET_BASE_URL")
            self._validate_https_url(
                "PASSWORD_RESET_BASE_URL",
                self.PASSWORD_RESET_BASE_URL,
                production=production,
            )

        if self.MAIL_DELIVERY_ENABLED and production:
            if not self.MAIL_UNSUBSCRIBE_BASE_URL:
                raise RuntimeError("Production marketing mail requires MAIL_UNSUBSCRIBE_BASE_URL")
            self._validate_https_url(
                "MAIL_UNSUBSCRIBE_BASE_URL",
                self.MAIL_UNSUBSCRIBE_BASE_URL,
                production=True,
            )
            if len(self.MAIL_UNSUBSCRIBE_HMAC_KEY) < 32 or _is_placeholder(self.MAIL_UNSUBSCRIBE_HMAC_KEY):
                raise RuntimeError(
                    "Production marketing mail requires a strong MAIL_UNSUBSCRIBE_HMAC_KEY"
                )

        if self.EMAIL_VERIFICATION_ENABLED:
            if not self.EMAIL_VERIFICATION_BASE_URL:
                raise RuntimeError("EMAIL_VERIFICATION_ENABLED requires EMAIL_VERIFICATION_BASE_URL")
            self._validate_https_url(
                "EMAIL_VERIFICATION_BASE_URL",
                self.EMAIL_VERIFICATION_BASE_URL,
                production=production,
            )


lifecycle_config = LifecycleConfig()
