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

from src.db.models.procurement import Procurement


class ProcurementRepository:
    """
    Operações de persistência para licitações."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, procurement: Procurement) -> Procurement:
        """Insere ou atualiza uma licitação pelo pncp_control_number."""
        stmt = (
            insert(Procurement)
            .values(
                pncp_control_number=procurement.pncp_control_number,
                procuring_entity_id=procurement.procuring_entity_id,
                procurement_object=procurement.procurement_object,
                additional_information=procurement.additional_information,
                estimated_price=procurement.estimated_price,
                tender_start_date=procurement.tender_start_date,
                tender_deadline=procurement.tender_deadline,
                published_at=procurement.published_at,
            )
            .on_conflict_do_update(
                index_elements=["pncp_control_number"],
                set_={
                    "procuring_entity_id": procurement.procuring_entity_id,
                    "procurement_object": procurement.procurement_object,
                    "additional_information": procurement.additional_information,
                    "estimated_price": procurement.estimated_price,
                    "tender_start_date": procurement.tender_start_date,
                    "tender_deadline": procurement.tender_deadline,
                    "published_at": procurement.published_at,
                },
            )
            .returning(Procurement)
        )

        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one()

    async def get_by_pncp_control_number(self, pncp_control_number: str) -> Procurement | None:
        """Busca uma licitação específica pelo número de controle do PNCP."""
        stmt = select(Procurement).where(
            Procurement.pncp_control_number == pncp_control_number
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_many_by_pncp_control_numbers(
        self,
        pncp_control_numbers: list[str],
    ) -> list[Procurement]:
        """Busca múltiplas licitações pelos seus números de controle do PNCP."""
        if not pncp_control_numbers:
            return []

        stmt = select(Procurement).where(
            Procurement.pncp_control_number.in_(pncp_control_numbers)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())