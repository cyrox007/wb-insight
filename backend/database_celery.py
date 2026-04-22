from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from settings import config

_engine = None
_sessionmaker = None


def get_engine():
    global _engine

    if _engine is None:
        _engine = create_async_engine(
            config.database_url(async_mode=True),
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=5,         # 👈 меньше, чем в API
            max_overflow=5,
        )

    return _engine


def get_sessionmaker():
    global _sessionmaker

    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
            class_=AsyncSession,
        )

    return _sessionmaker


async def get_session():
    session = get_sessionmaker()()

    # лёгкий ping
    await session.execute(text("SELECT 1"))

    return session