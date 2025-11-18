import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    SERVER_HTTP_PROTOCOL = os.getenv("SERVER_HTTP_PROTOCOL", "http://")
    SERVER_ADDR = os.getenv("SERVER_ADDR", "localhost")
    SERVER_PORT = os.getenv("SERVER_PORT", "9000")
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
        return f"{driver}://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
    
config = Config()