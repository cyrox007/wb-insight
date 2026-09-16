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

    SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip() or None
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD") or None
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "").strip()
    SMTP_STARTTLS = os.getenv("SMTP_STARTTLS", "true").lower() == "true"
    SMTP_TIMEOUT_SECONDS = float(os.getenv("SMTP_TIMEOUT_SECONDS", "10"))

    ACCOUNT_DEACTIVATION_RETENTION_DAYS = int(
        os.getenv("ACCOUNT_DEACTIVATION_RETENTION_DAYS", "90")
    )

    def validate(self, *, production: bool) -> None:
        if self.PASSWORD_RESET_TOKEN_TTL_MINUTES <= 0:
            raise RuntimeError("PASSWORD_RESET_TOKEN_TTL_MINUTES must be positive")
        if self.SMTP_PORT <= 0 or self.SMTP_TIMEOUT_SECONDS <= 0:
            raise RuntimeError("SMTP port and timeout must be positive")
        if self.ACCOUNT_DEACTIVATION_RETENTION_DAYS <= 0:
            raise RuntimeError("ACCOUNT_DEACTIVATION_RETENTION_DAYS must be positive")
        if not self.PASSWORD_RESET_ENABLED:
            return

        missing = [
            name
            for name, value in {
                "PASSWORD_RESET_BASE_URL": self.PASSWORD_RESET_BASE_URL,
                "SMTP_HOST": self.SMTP_HOST,
                "SMTP_FROM_EMAIL": self.SMTP_FROM_EMAIL,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(
                "PASSWORD_RESET_ENABLED requires: " + ", ".join(missing)
            )
        if bool(self.SMTP_USERNAME) != bool(self.SMTP_PASSWORD):
            raise RuntimeError("SMTP_USERNAME and SMTP_PASSWORD must be configured together")

        if not production:
            return

        reset_url = urlparse(self.PASSWORD_RESET_BASE_URL)
        if reset_url.scheme.lower() != "https" or not reset_url.hostname:
            raise RuntimeError("Production PASSWORD_RESET_BASE_URL must use https://")
        if "replace-with-" in reset_url.hostname.lower() or _is_reserved_example_host(reset_url.hostname):
            raise RuntimeError("Production PASSWORD_RESET_BASE_URL must use the real service host")
        if not self.SMTP_STARTTLS:
            raise RuntimeError("Production password recovery requires SMTP_STARTTLS=true")

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


lifecycle_config = LifecycleConfig()
