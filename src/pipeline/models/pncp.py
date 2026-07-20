"""
Pydantic models mirroring the PNCP API DTOs.

Why model here instead of using dicts directly?
- Automatic validation of data received from the API
- Explicit typing that documents the contract with the data source
- Facilitates serialization to Postgres and Milvus without manual transformations
- Temporal serializes/deserializes Activities via JSON — Pydantic handles this natively
"""

from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field


class ContractingAuthority(BaseModel):
    cnpj: str
    corporate_name: str = Field(alias="razaoSocial")
    power_id: Optional[str] = Field(default=None, alias="poderId")
    sphere_id: Optional[str] = Field(default=None, alias="esferaId")

    model_config = {"populate_by_name": True}


class ContractingUnit(BaseModel):
    state_name: Optional[str] = Field(default=None, alias="ufNome")
    state_acronym: Optional[str] = Field(default=None, alias="ufSigla")
    municipality_name: Optional[str] = Field(default=None, alias="municipioNome")
    unit_name: Optional[str] = Field(default=None, alias="nomeUnidade")
    unit_code: Optional[str] = Field(default=None, alias="codigoUnidade")
    ibge_code: Optional[str] = Field(default=None, alias="codigoIbge")

    model_config = {"populate_by_name": True}


class ProcurementDTO(BaseModel):
    """
    Represents a procurement returned by the PNCP API.
    Maps the RecuperarCompraPublicacaoDTO schema from the OpenAPI specification.

    The pncp_control_number field is the natural domain key —
    we use it as the ID in both Postgres and Milvus to ensure that
    the join between the two stores is simple and reliable.
    """
    pncp_control_number: str = Field(alias="numeroControlePNCP")
    procurement_object: str = Field(alias="objetoCompra")
    modality_id: Optional[int] = Field(default=None, alias="modalidadeId")
    modality_name: Optional[str] = Field(default=None, alias="modalidadeNome")
    dispute_mode_id: Optional[int] = Field(default=None, alias="modoDisputaId")
    dispute_mode_name: Optional[str] = Field(default=None, alias="modoDisputaNome")
    estimated_total_value: Optional[float] = Field(default=None, alias="valorTotalEstimado")
    approved_total_value: Optional[float] = Field(default=None, alias="valorTotalHomologado")
    procurement_status_id: Optional[int] = Field(default=None, alias="situacaoCompraId")
    procurement_status_name: Optional[str] = Field(default=None, alias="situacaoCompraNome")
    published_at_pncp: Optional[datetime] = Field(default=None, alias="dataPublicacaoPncp")
    proposal_start_date: Optional[datetime] = Field(default=None, alias="dataAberturaProposta")
    proposal_deadline: Optional[datetime] = Field(default=None, alias="dataEncerramentoProposta")
    updated_at: Optional[datetime] = Field(default=None, alias="dataAtualizacao")
    globally_updated_at: Optional[datetime] = Field(default=None, alias="dataAtualizacaoGlobal")
    contracting_authority: Optional[ContractingAuthority] = Field(default=None, alias="orgaoEntidade")
    contracting_unit: Optional[ContractingUnit] = Field(default=None, alias="unidadeOrgao")
    srp: Optional[bool] = None  # Price Registration System
    source_system_link: Optional[str] = Field(default=None, alias="linkSistemaOrigem")
    additional_information: Optional[str] = Field(default=None, alias="informacaoComplementar")

    model_config = {"populate_by_name": True}

    @property
    def proposal_open(self) -> bool:
        """
        Derived property — computed in real time to ensure accuracy.
        We do not store this as a fixed field because the time window changes constantly.
        In Milvus, we index the raw datetime and filter via expression.
        """
        if self.proposal_deadline is None:
            return False
        return self.proposal_deadline > datetime.now(self.proposal_deadline.tzinfo)

    @property
    def uf(self) -> Optional[str]:
        """Shortcut to easily access the state acronym in persistence layers."""
        return self.contracting_unit.state_acronym if self.contracting_unit else None

    @property
    def embedding_text(self) -> str:
        """
        Field that will be transformed into a vector.
        We concatenate the procurement object with the additional information because
        together they provide the richest semantic context for similarity search.
        """
        parts = [self.procurement_object]
        if self.additional_information:
            parts.append(self.additional_information)
        return " ".join(parts)


class ProcurementsPage(BaseModel):
    """Pagination envelope returned by the PNCP API."""
    data: list[ProcurementDTO] = Field(default_factory=list)
    total_records: int = Field(alias="totalRegistros", default=0)
    total_pages: int = Field(alias="totalPaginas", default=0)
    page_number: int = Field(alias="numeroPagina", default=1)
    empty: bool = False

    model_config = {"populate_by_name": True}
