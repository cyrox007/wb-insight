from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError
from sqlalchemy import text
from typing import AsyncGenerator
import asyncio

from core.logger import setup_logger
from settings import config

logger = setup_logger(__name__)

class Database:
    _engine = None
    _async_session_maker = None
    _engine_loop = None
    
    @classmethod
    def get_engine(cls):
        current_loop = asyncio.get_event_loop()

        if cls._engine is None or cls._engine_loop != current_loop:
            cls._engine = create_async_engine(
                config.database_url(async_mode=True),
                # Оптимизированные настройки пула
                pool_size=20,
                max_overflow=10,
                pool_timeout=30,
                pool_pre_ping=True,  # ✅ Хорошо!
                pool_recycle=300,    # ✅ Хорошо!
                
                # Дополнительные настройки
                echo=config.DEBUG,  # Логировать SQL только в DEBUG режиме
                echo_pool=config.DEBUG,
                
                # Важные настройки для асинхронности
                future=True,  # ✅ Обязательно для async
                
                # Настройки для стабильности
                connect_args={
                    "command_timeout": 60,
                    "server_settings": {
                        "application_name": "your_app_name"
                    }
                } if "postgresql" in config.database_url(async_mode=True) else {}
            )
            cls._engine_loop = current_loop
            
        return cls._engine
    
    @classmethod
    def sessionmaker(cls):
        if cls._async_session_maker is None:
            cls._async_session_maker = async_sessionmaker(
                bind=cls.get_engine(),
                expire_on_commit=False,  # ✅ Правильно!
                autoflush=False,         # ✅ Правильно!
                class_=AsyncSession,
                
                # Дополнительные настройки
                autobegin=True,  # Автоматически начинать транзакцию
            )
        return cls._async_session_maker
    
    @classmethod
    async def get_session(cls) -> AsyncSession:
        """Основной метод получения сессии с retry логикой"""
        max_retries = 3
        
        for attempt in range(max_retries):
            session: AsyncSession = cls.sessionmaker()()
            connection_successful = False
            
            try:
                # Проверка соединения
                await session.execute(text("SELECT 1"))
                #logger.debug("Database connection successful")
                connection_successful = True
                return session
                
            except (InterfaceError, OperationalError) as e:
                await session.close()
                logger.warning(f"Database connection attempt {attempt + 1} failed: {str(e)}")
                
                if attempt == max_retries - 1:
                    raise ConnectionError(f"Failed to connect to database after {max_retries} attempts") from e
                    
                await asyncio.sleep(2 ** attempt)
                
            except SQLAlchemyError as e:
                await session.close()
                logger.error(f"Unexpected database error: {str(e)}")
                raise
        
        # Теоретически недостижимый код, но для анализатора
        raise RuntimeError("Unexpected control flow")
    
    @classmethod
    async def session_generator(cls) -> AsyncGenerator[AsyncSession, None]:
        """Для FastAPI Depends с управлением транзакциями"""
        session = await cls.get_session()
        try:
            yield session
            await session.commit()  # ✅ Автокоммит при успешном завершении
        except Exception:
            await session.rollback()  # ✅ Автооткат при ошибках
            raise
        finally:
            await session.close()
    
    @classmethod
    async def health_check(cls) -> bool:
        """Проверка здоровья базы данных"""
        try:
            async with cls.sessionmaker()() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return False
    
    @classmethod
    async def dispose(cls):
        """Корректное освобождение ресурсов"""
        if cls._engine:
            await cls._engine.dispose()
            cls._engine = None
            cls._async_session_maker = None
            logger.info("Database engine disposed")

    # Base для моделей
    Base = declarative_base()