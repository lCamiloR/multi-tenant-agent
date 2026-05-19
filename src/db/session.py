"""
Configuração da sessão assíncrona do SQLAlchemy.

Centralizamos a engine e a factory de sessão aqui para que
FastAPI, Activities do Temporal e qualquer outro consumidor
importem sempre da mesma fonte — evitando múltiplas engines
apontando para o mesmo banco, o que causaria problemas de
connection pool.
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.core.config import SETTINGS

engine = create_async_engine(
    SETTINGS.database_url,
    echo=False,
    pool_size=10,        # conexões mantidas abertas no pool
    max_overflow=20,     # conexões extras permitidas sob carga
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    """
    Dependency injetável no FastAPI e nas Activities do Temporal.

    Uso no FastAPI:
        @router.get("/")
        async def route(session: AsyncSession = Depends(get_session)):
            ...

    Uso nas Activities:
        async with get_session() as session:
            await repo.upsert(session, item)
    """
    async with AsyncSessionFactory() as session:
        yield session