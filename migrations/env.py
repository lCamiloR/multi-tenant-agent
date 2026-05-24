"""
Configuração do ambiente de execução do Alembic.

Este arquivo é o ponto de entrada do Alembic — ele é executado
automaticamente pelos comandos `alembic revision` e `alembic upgrade`.

Duas configurações críticas aqui:
1. target_metadata: aponta para o Base.metadata que contém todos os
   models SQLAlchemy — sem isso o --autogenerate não detecta as tabelas.
2. engine async: usamos AsyncEngine porque o driver é asyncpg —
   o Alembic tem suporte nativo a isso via run_async_migrations().
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Importamos o Base e todos os models para que o metadata
# esteja populado quando o --autogenerate inspecionar o schema.
# IMPORTANTE: todos os models precisam ser importados aqui,
# caso contrário o autogenerate não os detecta.
from src.db.base import Base
from src.db.models.procurement import Procurement          # noqa: F401
from src.db.models.procuring_entity import ProcuringEntity  # noqa: F401

# Importamos as settings para obter a DATABASE_URL do .env
from src.core.config import SETTINGS

# Lê o alembic.ini para configuração de logging
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Aponta para o metadata que contém todas as tabelas declaradas nos models.
# É isso que permite o --autogenerate comparar o estado atual do banco
# com o estado esperado pelos models e gerar as migrations automaticamente.
target_metadata = Base.metadata

# Sobrescreve a sqlalchemy.url do alembic.ini com a variável de ambiente.
# Isso evita duplicar a URL de conexão em dois lugares.
config.set_main_option("sqlalchemy.url", SETTINGS.database_url)


def run_migrations_offline() -> None:
    """
    Modo offline: gera o SQL das migrations sem conectar ao banco.

    Útil para revisar o SQL antes de aplicar, ou para ambientes
    onde a conexão direta ao banco não está disponível.
    Execute com: alembic upgrade head --sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Modo online com engine assíncrona.

    Usamos async_engine_from_config em vez de engine_from_config
    porque o driver asyncpg não suporta uso síncrono — tentativas
    de usar create_engine() com asyncpg resultam no erro
    'Can't load plugin: sqlalchemy.dialects:driver' que você viu.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()