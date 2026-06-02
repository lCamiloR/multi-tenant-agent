"""
Repositório de acesso a dados para licitações e órgãos contratantes.

O padrão Repository centraliza toda a lógica de acesso ao banco neste módulo,
mantendo as Activities do Temporal e as rotas do FastAPI livres de queries SQL.
Isso tem dois benefícios práticos:

1. Testabilidade — você pode mockar o repositório nos testes sem precisar
   de um banco real rodando.
2. Manutenção — se a query de upsert precisar mudar, o único lugar a alterar
   é aqui, não espalhado pelas Activities.

Todas as operações são assíncronas porque tanto o FastAPI quanto o Temporal
rodam em event loop assíncrono — chamadas síncronas bloqueariam o loop inteiro.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from src.db.models.procuring_entity import ProcuringEntity


class ProcuringEntityRepository:
    """Operações de persistência para órgãos contratantes."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, entity: ProcuringEntity) -> ProcuringEntity:
        """Insere ou atualiza um órgão contratante pelo CNPJ."""
        stmt = (
            insert(ProcuringEntity)
            .values(
                cnpj=entity.cnpj,
                ibge_code=entity.ibge_code,
                state_name=entity.state_name,
                state_acronym=entity.state_acronym,
                unit_code=entity.unit_code,
                unit_name=entity.unit_name,
                municipality_name=entity.municipality_name,
            )
            .on_conflict_do_update(
                index_elements=["cnpj"],
                set_={
                    "ibge_code": entity.ibge_code,
                    "state_name": entity.state_name,
                    "state_acronym": entity.state_acronym,
                    "unit_code": entity.unit_code,
                    "unit_name": entity.unit_name,
                    "municipality_name": entity.municipality_name,
                },
            )
            .returning(ProcuringEntity)
        )

        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_by_cnpj(self, cnpj: str) -> ProcuringEntity | None:
        """Busca um órgão pelo CNPJ."""
        stmt = select(ProcuringEntity).where(ProcuringEntity.cnpj == cnpj)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()