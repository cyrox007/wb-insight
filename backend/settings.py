import os
from typing import Optional
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

class Config:
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    SERVER_HTTP_PROTOCOL = os.getenv("SERVER_HTTP_PROTOCOL", "http://")
    SERVER_ADDR = os.getenv("SERVER_ADDR", "localhost")
    SERVER_PORT = os.getenv("SERVER_PORT", "9000")

    @property
    def get_allowed_origins(self) -> list[str]:
        origins = os.getenv("ALLOWED_ORIGINS", "")
        return [origin.strip() for origin in origins.split(",") if origin.strip()]
    
    @property
    def BASE_URL(self):
        """
        Возвращает базовый URL сервера.
        Если порт стандартный (80 для HTTP, 443 для HTTPS), он не добавляется.
        """
        protocol = self.SERVER_HTTP_PROTOCOL
        address = self.SERVER_ADDR
        port = self.SERVER_PORT

        # Исключаем порт, если он стандартный
        if port in ["80", "443"]:
            return f"{protocol}{address}"
        return f"{protocol}{address}:{port}"
    
    # Database
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "wb")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

    def database_url(self, async_mode=False):
        driver = "postgresql+asyncpg" if async_mode else "postgresql"
        password = quote_plus(self.DB_PASSWORD)
        url = f"{driver}://{self.DB_USER}:{password}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        return url.replace("%", "%%")
    
    # Безопасность
    ENCRYPTION_KEY = os.getenv("API_TOKEN_ENCRYPTION_KEY")
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Wildberries API
    WB_API_BASE_URL: str = "https://statistics-api.wildberries.ru"
    WB_ADVERT_API_BASE_URL: str = "https://advert-api.wildberries.ru"
    
    # Celery
    CELERY_BROKER_URL: str = REDIS_URL
    CELERY_RESULT_BACKEND: str = REDIS_URL

    # Настройки JWT
    SECRET_KEY = os.getenv("JWT_SECRET_KEY") or 'your-secret-key-change-in-production'
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    
config = Config()