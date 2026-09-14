import os
from urllib.parse import quote_plus

from dotenv import load_dotenv


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

    # Database
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

    # Security secrets
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

    # Redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Wildberries API
    WB_API_BASE_URL = "https://statistics-api.wildberries.ru"
    WB_ADVERT_API_BASE_URL = "https://advert-api.wildberries.ru"

    # Celery
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL


config = Config()
