"""
Data access repository for procurements and procuring entities.

The Repository pattern centralizes all database access logic in this module,
keeping Temporal Activities and FastAPI routes free of raw SQL queries.
This provides two practical benefits:

1. Testability — you can mock the repository in tests without needing
   a real database running.
2. Maintainability — if the upsert query needs to change, the only place
   to update is here, not scattered across Activities.

All operations are async because both FastAPI and Temporal
run in an async event loop — synchronous calls would block the entire loop.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from src.db.models.procuring_entity import ProcuringEntity


class ProcuringEntityRepository:
    """Persistence operations for procuring entities."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, entity: ProcuringEntity) -> ProcuringEntity:
        """Inserts or updates a procuring entity by CNPJ."""
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
        """Fetches a procuring entity by CNPJ."""
        stmt = select(ProcuringEntity).where(ProcuringEntity.cnpj == cnpj)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
