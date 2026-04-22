from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from settings import config

engine = create_async_engine(
    config.database_url(async_mode=True),
    pool_pre_ping=True,
    pool_recycle=300,
    poolclass=NullPool
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

async def get_session():
    return SessionLocal()