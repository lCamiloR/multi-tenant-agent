"""
Maps external PNCP DTOs to internal ORM models.

This module is the single point of responsibility for translating
the external world (PNCP API schema) into our internal domain.
If the API changes or the database schema evolves, only this file needs
to change — Activities and repositories remain untouched.

Design principle: pure functions, no I/O, fully testable in isolation.
"""

from src.pipeline.models.pncp import ProcurementDTO
from src.db.models.procurement import Procurement
from src.db.models.procuring_entity import ProcuringEntity


def to_procuring_entity(dto: ProcurementDTO) -> ProcuringEntity:
    """
    Builds a ProcuringEntity ORM instance from a ProcurementDTO.

    Note: 'id' is intentionally omitted — SQLAlchemy/Postgres handles
    primary key assignment. The upsert uses 'cnpj' as the natural key.
    """
    unit = dto.contracting_unit
    authority = dto.contracting_authority

    return ProcuringEntity(
        cnpj=authority.cnpj if authority else "",
        ibge_code=int(unit.ibge_code) if unit and unit.ibge_code else 0,
        state_name=unit.state_name or "" if unit else "",
        state_acronym=unit.state_acronym or "" if unit else "",
        unit_code=unit.unit_code or "" if unit else "",
        unit_name=unit.unit_name or "" if unit else "",
        municipality_name=unit.municipality_name or "" if unit else "",
    )


def to_procurement(dto: ProcurementDTO, procuring_entity_id: int) -> Procurement:
    """
    Builds a Procurement ORM instance from a ProcurementDTO.

    Receives procuring_entity_id explicitly because this function is pure —
    it does not perform any database lookup. The caller (Activity) is
    responsible for resolving the FK before calling this function.

    This makes the mapping logic fully testable without a database.
    """
    return Procurement(
        pncp_control_number=dto.pncp_control_number,
        procuring_entity_id=procuring_entity_id,
        procurement_object=dto.procurement_object,
        additional_information=dto.additional_information or "",
        estimated_price=dto.estimated_total_value,
        tender_start_date=dto.proposal_start_date,
        tender_deadline=dto.proposal_deadline,
        published_at=dto.published_at_pncp,
    )
