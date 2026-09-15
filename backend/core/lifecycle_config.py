import os


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
        if production and not self.PASSWORD_RESET_BASE_URL.startswith("https://"):
            raise RuntimeError("Production PASSWORD_RESET_BASE_URL must use https://")
        if bool(self.SMTP_USERNAME) != bool(self.SMTP_PASSWORD):
            raise RuntimeError("SMTP_USERNAME and SMTP_PASSWORD must be configured together")


lifecycle_config = LifecycleConfig()
