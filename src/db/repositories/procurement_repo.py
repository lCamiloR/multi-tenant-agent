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

from src.db.models.procurement import Procurement


class ProcurementRepository:
    """Persistence operations for procurements."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, procurement: Procurement) -> Procurement:
        """Inserts or updates a procurement by pncp_control_number."""
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
        return result.scalar_one()

    async def get_by_pncp_control_number(self, pncp_control_number: str) -> Procurement | None:
        """Fetches a specific procurement by its PNCP control number."""
        stmt = select(Procurement).where(
            Procurement.pncp_control_number == pncp_control_number
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_many_by_pncp_control_numbers(
        self,
        pncp_control_numbers: list[str],
    ) -> list[Procurement]:
        """Fetches multiple procurements by their PNCP control numbers."""
        if not pncp_control_numbers:
            return []

        stmt = select(Procurement).where(
            Procurement.pncp_control_number.in_(pncp_control_numbers)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
