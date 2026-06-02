from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from packages.core.config import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
    future=True
)

# Create async session factory
AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db() -> AsyncSession:
    """
    FastAPI dependency for database sessions.
    
    Yields:
        AsyncSession instance
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
        finally:
            await session.close()
