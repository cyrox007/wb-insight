import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

from core.production_config import validate_production_config


load_dotenv()


class Config:
    APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
    IS_PRODUCTION = APP_ENV == "production"
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    PATH_TO_DIR = os.path.dirname(os.path.abspath(__file__))

    SERVER_HTTP_PROTOCOL = os.getenv("SERVER_HTTP_PROTOCOL", "http://")
    SERVER_ADDR = os.getenv("SERVER_ADDR", "localhost")
    SERVER_PORT = os.getenv("SERVER_PORT", "9000")

    @property
    def get_allowed_origins(self) -> list[str]:
        origins = os.getenv("ALLOWED_ORIGINS", "")
        return [origin.strip() for origin in origins.split(",") if origin.strip()]

    @property
    def BASE_URL(self) -> str:
        protocol = self.SERVER_HTTP_PROTOCOL
        address = self.SERVER_ADDR
        port = self.SERVER_PORT
        if port in ["80", "443"]:
            return f"{protocol}{address}"
        return f"{protocol}{address}:{port}"

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "wb")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

    def database_url(self, async_mode: bool = False) -> str:
        driver = "postgresql+asyncpg" if async_mode else "postgresql"
        password = quote_plus(self.DB_PASSWORD)
        url = f"{driver}://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        return url.replace("%", "%%")

    ENCRYPTION_KEY = os.getenv("API_TOKEN_ENCRYPTION_KEY")
    SECRET_KEY = os.getenv("JWT_SECRET_KEY")

    if not SECRET_KEY:
        raise RuntimeError("JWT_SECRET_KEY is required")
    if IS_PRODUCTION and not ENCRYPTION_KEY:
        raise RuntimeError("API_TOKEN_ENCRYPTION_KEY is required when APP_ENV=production")

    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

    if ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")
    if REFRESH_TOKEN_EXPIRE_DAYS <= 0:
        raise RuntimeError("REFRESH_TOKEN_EXPIRE_DAYS must be positive")

    REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "refresh_token")
    COOKIE_SECURE = os.getenv(
        "COOKIE_SECURE",
        "true" if IS_PRODUCTION else "false",
    ).lower() == "true"
    COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax").strip().lower()
    if COOKIE_SAMESITE not in {"lax", "strict", "none"}:
        raise RuntimeError("COOKIE_SAMESITE must be one of: lax, strict, none")
    if COOKIE_SAMESITE == "none" and not COOKIE_SECURE:
        raise RuntimeError("COOKIE_SECURE must be true when COOKIE_SAMESITE=none")
    if IS_PRODUCTION and not COOKIE_SECURE:
        raise RuntimeError("COOKIE_SECURE must be true when APP_ENV=production")
    COOKIE_DOMAIN = os.getenv("COOKIE_DOMAIN") or None

    ALLOW_FAKE_BILLING = (
        not IS_PRODUCTION
        and os.getenv("ALLOW_FAKE_BILLING", "false").lower() == "true"
    )

    SBER_ACQUIRING_ENABLED = os.getenv("SBER_ACQUIRING_ENABLED", "false").lower() == "true"
    SBER_API_BASE_URL = os.getenv(
        "SBER_API_BASE_URL",
        "https://ecomift.sberbank.ru/ecomm/gw/partner/api/v1",
    ).strip().rstrip("/")
    SBER_USERNAME = os.getenv("SBER_USERNAME", "").strip() or None
    SBER_PASSWORD = os.getenv("SBER_PASSWORD", "").strip() or None
    SBER_RETURN_URL = os.getenv("SBER_RETURN_URL", "").strip() or None
    SBER_FAIL_URL = os.getenv("SBER_FAIL_URL", "").strip() or None
    SBER_CURRENCY_CODE = os.getenv("SBER_CURRENCY_CODE", "643").strip()
    SBER_HTTP_TIMEOUT_SECONDS = float(os.getenv("SBER_HTTP_TIMEOUT_SECONDS", "10.0"))

    if SBER_ACQUIRING_ENABLED:
        missing_sber = [
            name
            for name, value in {
                "SBER_USERNAME": SBER_USERNAME,
                "SBER_PASSWORD": SBER_PASSWORD,
                "SBER_RETURN_URL": SBER_RETURN_URL,
                "SBER_FAIL_URL": SBER_FAIL_URL,
            }.items()
            if not value
        ]
        if missing_sber:
            raise RuntimeError(
                "SBER_ACQUIRING_ENABLED requires: " + ", ".join(missing_sber)
            )
        if SBER_HTTP_TIMEOUT_SECONDS <= 0:
            raise RuntimeError("SBER_HTTP_TIMEOUT_SECONDS must be positive")
        if IS_PRODUCTION and "ecomift.sberbank.ru" in SBER_API_BASE_URL:
            raise RuntimeError(
                "Production cannot use the Sber acquiring sandbox endpoint"
            )

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # WB requires partner services to identify themselves with a service ID and
    # sign seller-data requests with X-Client-Secret. This applies to Base and
    # Service seller tokens; production must therefore fail closed without both.
    WB_SERVICE_ID = os.getenv("WB_SERVICE_ID", "").strip() or None
    WB_SERVICE_SECRET = os.getenv("WB_SERVICE_SECRET", "").strip() or None
    if bool(WB_SERVICE_ID) != bool(WB_SERVICE_SECRET):
        raise RuntimeError(
            "WB_SERVICE_ID and WB_SERVICE_SECRET must be configured together"
        )
    if IS_PRODUCTION and (not WB_SERVICE_ID or not WB_SERVICE_SECRET):
        raise RuntimeError(
            "WB_SERVICE_ID and WB_SERVICE_SECRET are required in production"
        )

    WB_API_BASE_URL = "https://statistics-api.wildberries.ru"
    WB_ADVERT_API_BASE_URL = "https://advert-api.wildberries.ru"
    WB_SELLER_ANALYTICS_API_BASE_URL = "https://seller-analytics-api.wildberries.ru"

    # Generic fallback for WB methods without an explicit documented policy.
    WB_API_MIN_INTERVAL_SECONDS = float(
        os.getenv("WB_API_MIN_INTERVAL_SECONDS", "1.0")
    )
    # Documented per-account intervals for the endpoints used by the sync engine.
    WB_FINANCE_MIN_INTERVAL_SECONDS = float(
        os.getenv("WB_FINANCE_MIN_INTERVAL_SECONDS", "60.0")
    )
    WB_STOCKS_MIN_INTERVAL_SECONDS = float(
        os.getenv("WB_STOCKS_MIN_INTERVAL_SECONDS", "20.0")
    )
    WB_CONTENT_CARDS_MIN_INTERVAL_SECONDS = float(
        os.getenv("WB_CONTENT_CARDS_MIN_INTERVAL_SECONDS", "0.6")
    )
    WB_PRICES_MIN_INTERVAL_SECONDS = float(
        os.getenv("WB_PRICES_MIN_INTERVAL_SECONDS", "0.6")
    )
    WB_OPERATIONAL_MIN_INTERVAL_SECONDS = float(
        os.getenv("WB_OPERATIONAL_MIN_INTERVAL_SECONDS", "60.0")
    )
    WB_ADVERT_CAMPAIGNS_MIN_INTERVAL_SECONDS = float(
        os.getenv("WB_ADVERT_CAMPAIGNS_MIN_INTERVAL_SECONDS", "0.2")
    )
    WB_ADVERT_STATS_MIN_INTERVAL_SECONDS = float(
        os.getenv("WB_ADVERT_STATS_MIN_INTERVAL_SECONDS", "20.0")
    )
    WB_ADVERT_LOOKBACK_DAYS = int(os.getenv("WB_ADVERT_LOOKBACK_DAYS", "31"))
    WB_FUNNEL_MIN_INTERVAL_SECONDS = float(
        os.getenv("WB_FUNNEL_MIN_INTERVAL_SECONDS", "20.0")
    )
    WB_FUNNEL_LOOKBACK_DAYS = int(os.getenv("WB_FUNNEL_LOOKBACK_DAYS", "7"))
    WB_FUNNEL_NM_BATCH_SIZE = int(os.getenv("WB_FUNNEL_NM_BATCH_SIZE", "20"))
    WB_STORAGE_CREATE_MIN_INTERVAL_SECONDS = float(
        os.getenv("WB_STORAGE_CREATE_MIN_INTERVAL_SECONDS", "60.0")
    )
    WB_STORAGE_STATUS_MIN_INTERVAL_SECONDS = float(
        os.getenv("WB_STORAGE_STATUS_MIN_INTERVAL_SECONDS", "5.0")
    )
    WB_STORAGE_DOWNLOAD_MIN_INTERVAL_SECONDS = float(
        os.getenv("WB_STORAGE_DOWNLOAD_MIN_INTERVAL_SECONDS", "60.0")
    )
    WB_STORAGE_BACKFILL_DAYS = int(os.getenv("WB_STORAGE_BACKFILL_DAYS", "30"))
    WB_STORAGE_REFRESH_DAYS = int(os.getenv("WB_STORAGE_REFRESH_DAYS", "8"))
    WB_STORAGE_STATUS_MAX_POLLS = int(os.getenv("WB_STORAGE_STATUS_MAX_POLLS", "36"))

    WB_API_MAX_ATTEMPTS = int(os.getenv("WB_API_MAX_ATTEMPTS", "4"))
    WB_API_BACKOFF_BASE_SECONDS = float(
        os.getenv("WB_API_BACKOFF_BASE_SECONDS", "1.0")
    )
    WB_API_MAX_BACKOFF_SECONDS = float(
        os.getenv("WB_API_MAX_BACKOFF_SECONDS", "60.0")
    )

    # Durable sync execution. The lease is intentionally longer than the
    # Celery hard task limit (30 minutes) so another poller never reclaims a
    # still-running job. A killed worker is recovered after lease expiry.
    SYNC_JOB_LEASE_SECONDS = int(os.getenv("SYNC_JOB_LEASE_SECONDS", "2100"))
    SYNC_JOB_MAX_ATTEMPTS = int(os.getenv("SYNC_JOB_MAX_ATTEMPTS", "3"))
    SYNC_JOB_RETRY_BASE_SECONDS = int(
        os.getenv("SYNC_JOB_RETRY_BASE_SECONDS", "60")
    )
    SYNC_JOB_RETRY_MAX_SECONDS = int(
        os.getenv("SYNC_JOB_RETRY_MAX_SECONDS", "900")
    )

    for setting_name, interval in {
        "WB_API_MIN_INTERVAL_SECONDS": WB_API_MIN_INTERVAL_SECONDS,
        "WB_FINANCE_MIN_INTERVAL_SECONDS": WB_FINANCE_MIN_INTERVAL_SECONDS,
        "WB_STOCKS_MIN_INTERVAL_SECONDS": WB_STOCKS_MIN_INTERVAL_SECONDS,
        "WB_CONTENT_CARDS_MIN_INTERVAL_SECONDS": WB_CONTENT_CARDS_MIN_INTERVAL_SECONDS,
        "WB_PRICES_MIN_INTERVAL_SECONDS": WB_PRICES_MIN_INTERVAL_SECONDS,
        "WB_OPERATIONAL_MIN_INTERVAL_SECONDS": WB_OPERATIONAL_MIN_INTERVAL_SECONDS,
        "WB_ADVERT_CAMPAIGNS_MIN_INTERVAL_SECONDS": WB_ADVERT_CAMPAIGNS_MIN_INTERVAL_SECONDS,
        "WB_ADVERT_STATS_MIN_INTERVAL_SECONDS": WB_ADVERT_STATS_MIN_INTERVAL_SECONDS,
        "WB_FUNNEL_MIN_INTERVAL_SECONDS": WB_FUNNEL_MIN_INTERVAL_SECONDS,
        "WB_STORAGE_CREATE_MIN_INTERVAL_SECONDS": WB_STORAGE_CREATE_MIN_INTERVAL_SECONDS,
        "WB_STORAGE_STATUS_MIN_INTERVAL_SECONDS": WB_STORAGE_STATUS_MIN_INTERVAL_SECONDS,
        "WB_STORAGE_DOWNLOAD_MIN_INTERVAL_SECONDS": WB_STORAGE_DOWNLOAD_MIN_INTERVAL_SECONDS,
    }.items():
        if interval < 0:
            raise RuntimeError(f"{setting_name} cannot be negative")

    if WB_ADVERT_LOOKBACK_DAYS < 1 or WB_ADVERT_LOOKBACK_DAYS > 31:
        raise RuntimeError("WB_ADVERT_LOOKBACK_DAYS must be between 1 and 31")
    if WB_FUNNEL_LOOKBACK_DAYS < 1 or WB_FUNNEL_LOOKBACK_DAYS > 7:
        raise RuntimeError("WB_FUNNEL_LOOKBACK_DAYS must be between 1 and 7")
    if WB_FUNNEL_NM_BATCH_SIZE < 1 or WB_FUNNEL_NM_BATCH_SIZE > 20:
        raise RuntimeError("WB_FUNNEL_NM_BATCH_SIZE must be between 1 and 20")
    if WB_STORAGE_BACKFILL_DAYS < 1:
        raise RuntimeError("WB_STORAGE_BACKFILL_DAYS must be positive")
    if WB_STORAGE_REFRESH_DAYS < 1 or WB_STORAGE_REFRESH_DAYS > 8:
        raise RuntimeError("WB_STORAGE_REFRESH_DAYS must be between 1 and 8")
    if WB_STORAGE_STATUS_MAX_POLLS < 1:
        raise RuntimeError("WB_STORAGE_STATUS_MAX_POLLS must be positive")
    if WB_API_MAX_ATTEMPTS <= 0:
        raise RuntimeError("WB_API_MAX_ATTEMPTS must be positive")
    if WB_API_BACKOFF_BASE_SECONDS <= 0:
        raise RuntimeError("WB_API_BACKOFF_BASE_SECONDS must be positive")
    if WB_API_MAX_BACKOFF_SECONDS < WB_API_BACKOFF_BASE_SECONDS:
        raise RuntimeError(
            "WB_API_MAX_BACKOFF_SECONDS must be >= WB_API_BACKOFF_BASE_SECONDS"
        )
    if SYNC_JOB_LEASE_SECONDS <= 0:
        raise RuntimeError("SYNC_JOB_LEASE_SECONDS must be positive")
    if SYNC_JOB_MAX_ATTEMPTS <= 0:
        raise RuntimeError("SYNC_JOB_MAX_ATTEMPTS must be positive")
    if SYNC_JOB_RETRY_BASE_SECONDS <= 0:
        raise RuntimeError("SYNC_JOB_RETRY_BASE_SECONDS must be positive")
    if SYNC_JOB_RETRY_MAX_SECONDS < SYNC_JOB_RETRY_BASE_SECONDS:
        raise RuntimeError(
            "SYNC_JOB_RETRY_MAX_SECONDS must be >= SYNC_JOB_RETRY_BASE_SECONDS"
        )

    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL


config = Config()
validate_production_config(config)
