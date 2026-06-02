"""
Maps external PNCP DTOs to internal ORM models.

This module is the single point of responsibility for translating
the external world (PNCP API schema) into our internal domain.
If the API changes or the database schema evolves, only this file needs
to change — Activities and repositories remain untouched.

Design principle: pure functions, no I/O, fully testable in isolation.
"""

from src.pipeline.models.pncp import ContratacaoDTO
from src.db.models.procurement import Procurement
from src.db.models.procuring_entity import ProcuringEntity


def to_procuring_entity(dto: ContratacaoDTO) -> ProcuringEntity:
    """
    Builds a ProcuringEntity ORM instance from a ContratacaoDTO.

    Note: 'id' is intentionally omitted — SQLAlchemy/Postgres handles
    primary key assignment. The upsert uses 'cnpj' as the natural key.
    """
    unidade = dto.unidade_orgao
    orgao = dto.orgao_entidade

    return ProcuringEntity(
        cnpj=orgao.cnpj if orgao else "",
        ibge_code=int(unidade.codigo_ibge) if unidade and unidade.codigo_ibge else 0,
        state_name=unidade.uf_nome or "" if unidade else "",
        state_acronym=unidade.uf_sigla or "" if unidade else "",
        unit_code=unidade.codigo_unidade or "" if unidade else "",
        unit_name=unidade.nome_unidade or "" if unidade else "",
        municipality_name=unidade.municipio_nome or "" if unidade else "",
    )


def to_procurement(dto: ContratacaoDTO, procuring_entity_id: int) -> Procurement:
    """
    Builds a Procurement ORM instance from a ContratacaoDTO.

    Receives procuring_entity_id explicitly because this function is pure —
    it does not perform any database lookup. The caller (Activity) is
    responsible for resolving the FK before calling this function.

    This makes the mapping logic fully testable without a database.
    """
    return Procurement(
        pncp_control_number=dto.numero_controle_pncp,
        procuring_entity_id=procuring_entity_id,
        procurement_object=dto.objeto_compra,
        additional_information=dto.informacao_complementar or "",
        estimated_price=dto.valor_total_estimado,
        tender_start_date=dto.data_abertura_proposta,
        tender_deadline=dto.data_encerramento_proposta,
        published_at=dto.data_publicacao_pncp,
    )