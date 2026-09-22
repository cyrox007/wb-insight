import asyncio
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

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
                # Параметры пула соединений.
                pool_size=20,
                max_overflow=10,
                pool_timeout=30,
                pool_pre_ping=True,
                pool_recycle=300,
                # SQL-запросы и состояние пула логируются только в режиме DEBUG.
                echo=config.DEBUG,
                echo_pool=config.DEBUG,
                # SQLAlchemy 2.x использует современный режим работы по умолчанию.
                future=True,
                # Параметры устойчивости соединения с PostgreSQL.
                connect_args={
                    "command_timeout": 60,
                    "server_settings": {
                        "application_name": "wb-insight"
                    },
                } if "postgresql" in config.database_url(async_mode=True) else {},
            )
            cls._engine_loop = current_loop

        return cls._engine

    @classmethod
    def sessionmaker(cls):
        if cls._async_session_maker is None:
            cls._async_session_maker = async_sessionmaker(
                bind=cls.get_engine(),
                expire_on_commit=False,
                autoflush=False,
                class_=AsyncSession,
                # Транзакция начинается автоматически при первом обращении к БД.
                autobegin=True,
            )
        return cls._async_session_maker

    @classmethod
    async def get_session(cls) -> AsyncSession:
        """Возвращает рабочую сессию БД с повторными попытками подключения."""
        max_retries = 3

        for attempt in range(max_retries):
            session: AsyncSession = cls.sessionmaker()()

            try:
                # Простая проверка соединения до передачи сессии вызывающему коду.
                await session.execute(text("SELECT 1"))
                return session

            except (InterfaceError, OperationalError) as exc:
                await session.close()
                logger.warning(
                    "Попытка подключения к базе данных %s завершилась ошибкой: %s",
                    attempt + 1,
                    exc,
                )

                if attempt == max_retries - 1:
                    raise ConnectionError(
                        f"Не удалось подключиться к базе данных после {max_retries} попыток"
                    ) from exc

                await asyncio.sleep(2 ** attempt)

            except SQLAlchemyError as exc:
                await session.close()
                logger.error("Непредвиденная ошибка базы данных: %s", exc)
                raise

        # Защитная ветка: штатный цикл всегда возвращает сессию или выбрасывает ошибку.
        raise RuntimeError("Недостижимое состояние получения сессии базы данных")

    @classmethod
    async def session_generator(cls) -> AsyncGenerator[AsyncSession, None]:
        """Предоставляет FastAPI-сессию с автоматической фиксацией или откатом транзакции."""
        session = await cls.get_session()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @classmethod
    async def health_check(cls) -> bool:
        """Проверяет доступность базы данных."""
        try:
            async with cls.sessionmaker()() as session:
                result = await session.execute(text("SELECT 1"))
                return result.scalar() == 1
        except Exception as exc:
            logger.error("Проверка доступности базы данных завершилась ошибкой: %s", exc)
            return False

    @classmethod
    async def dispose(cls):
        """Корректно освобождает ресурсы подключения к базе данных."""
        if cls._engine:
            await cls._engine.dispose()
            cls._engine = None
            cls._async_session_maker = None
            logger.info("Ресурсы подключения к базе данных освобождены")

    # Базовый класс SQLAlchemy для моделей.
    Base = declarative_base()
