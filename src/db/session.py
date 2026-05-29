from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from src.core.config import SETTINGS

engine = create_async_engine(
    SETTINGS.database_url,
    echo=False,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency. Use exclusively with Depends():

        async def route(session: AsyncSession = Depends(get_session)): ...

    For Temporal Activities or standalone scripts, use get_session_ctx() instead.
    """
    async with AsyncSessionFactory() as session:
        yield session


def get_session_ctx():
    """
    Async context manager for use outside of FastAPI (Temporal Activities, scripts, tests).

    Usage:
        async with get_session_ctx() as session:
            await repo.upsert(session, item)
    """
    return AsyncSessionFactory()