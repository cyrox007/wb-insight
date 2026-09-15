import os
from urllib.parse import urlparse


class OpsConfig:
    SYNC_STALE_MINUTES = int(os.getenv("OPS_SYNC_STALE_MINUTES", "180"))
    FAILED_JOB_LOOKBACK_MINUTES = int(
        os.getenv("OPS_FAILED_JOB_LOOKBACK_MINUTES", "60")
    )
    CREDENTIAL_EXPIRY_WARNING_DAYS = int(
        os.getenv("OPS_CREDENTIAL_EXPIRY_WARNING_DAYS", "14")
    )
    WB_SERVICE_SECRET_EXPIRY_WARNING_DAYS = int(
        os.getenv("OPS_WB_SERVICE_SECRET_EXPIRY_WARNING_DAYS", "30")
    )
    WB_SERVICE_SECRET_EXPIRES_AT = (
        os.getenv("OPS_WB_SERVICE_SECRET_EXPIRES_AT", "").strip() or None
    )
    HTTP_METRICS_ENABLED = os.getenv("OPS_HTTP_METRICS_ENABLED", "false").lower() == "true"
    HTTP_ERROR_WINDOW_MINUTES = int(
        os.getenv("OPS_HTTP_ERROR_WINDOW_MINUTES", "5")
    )
    HTTP_5XX_RATE_THRESHOLD = float(
        os.getenv("OPS_HTTP_5XX_RATE_THRESHOLD", "0.05")
    )
    HTTP_MIN_REQUESTS = int(os.getenv("OPS_HTTP_MIN_REQUESTS", "20"))
    ALERT_CHECK_INTERVAL_SECONDS = int(
        os.getenv("OPS_ALERT_CHECK_INTERVAL_SECONDS", "900")
    )
    ALERT_REPEAT_SECONDS = int(os.getenv("OPS_ALERT_REPEAT_SECONDS", "3600"))
    ALERT_WEBHOOK_URL = os.getenv("OPS_ALERT_WEBHOOK_URL", "").strip() or None
    ALERT_WEBHOOK_TIMEOUT_SECONDS = float(
        os.getenv("OPS_ALERT_WEBHOOK_TIMEOUT_SECONDS", "5")
    )

    if SYNC_STALE_MINUTES <= 0:
        raise RuntimeError("OPS_SYNC_STALE_MINUTES must be positive")
    if FAILED_JOB_LOOKBACK_MINUTES <= 0:
        raise RuntimeError("OPS_FAILED_JOB_LOOKBACK_MINUTES must be positive")
    if CREDENTIAL_EXPIRY_WARNING_DAYS <= 0:
        raise RuntimeError("OPS_CREDENTIAL_EXPIRY_WARNING_DAYS must be positive")
    if WB_SERVICE_SECRET_EXPIRY_WARNING_DAYS <= 0:
        raise RuntimeError(
            "OPS_WB_SERVICE_SECRET_EXPIRY_WARNING_DAYS must be positive"
        )
    if HTTP_ERROR_WINDOW_MINUTES <= 0 or HTTP_ERROR_WINDOW_MINUTES > 60:
        raise RuntimeError("OPS_HTTP_ERROR_WINDOW_MINUTES must be between 1 and 60")
    if not 0 <= HTTP_5XX_RATE_THRESHOLD <= 1:
        raise RuntimeError("OPS_HTTP_5XX_RATE_THRESHOLD must be between 0 and 1")
    if HTTP_MIN_REQUESTS <= 0:
        raise RuntimeError("OPS_HTTP_MIN_REQUESTS must be positive")
    if ALERT_CHECK_INTERVAL_SECONDS < 60:
        raise RuntimeError("OPS_ALERT_CHECK_INTERVAL_SECONDS must be at least 60")
    if ALERT_REPEAT_SECONDS < ALERT_CHECK_INTERVAL_SECONDS:
        raise RuntimeError(
            "OPS_ALERT_REPEAT_SECONDS must be >= OPS_ALERT_CHECK_INTERVAL_SECONDS"
        )
    if ALERT_WEBHOOK_TIMEOUT_SECONDS <= 0:
        raise RuntimeError("OPS_ALERT_WEBHOOK_TIMEOUT_SECONDS must be positive")
    if ALERT_WEBHOOK_URL:
        parsed = urlparse(ALERT_WEBHOOK_URL)
        if parsed.scheme != "https" or not parsed.netloc:
            raise RuntimeError("OPS_ALERT_WEBHOOK_URL must be an absolute HTTPS URL")


ops_config = OpsConfig()
