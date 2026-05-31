"""
Modelos Pydantic que espelham os DTOs da API do PNCP.

Por que modelar aqui e não usar dicts direto?
- Validação automática dos dados recebidos da API
- Tipagem explícita que documenta o contrato com a fonte de dados
- Facilita a serialização para Postgres e Milvus sem transformações manuais
- O Temporal serializa/deserializa Activities via JSON — Pydantic lida com isso nativamente
"""

from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field


class OrgaoEntidade(BaseModel):
    cnpj: str
    razao_social: str = Field(alias="razaoSocial")
    poder_id: Optional[str] = Field(default=None, alias="poderId")
    esfera_id: Optional[str] = Field(default=None, alias="esferaId")

    model_config = {"populate_by_name": True}


class UnidadeOrgao(BaseModel):
    uf_nome: Optional[str] = Field(default=None, alias="ufNome")
    uf_sigla: Optional[str] = Field(default=None, alias="ufSigla")
    municipio_nome: Optional[str] = Field(default=None, alias="municipioNome")
    nome_unidade: Optional[str] = Field(default=None, alias="nomeUnidade")
    codigo_unidade: Optional[str] = Field(default=None, alias="codigoUnidade")
    codigo_ibge: Optional[str] = Field(default=None, alias="codigoIbge")

    model_config = {"populate_by_name": True}


class ContratacaoDTO(BaseModel):
    """
    Representa uma contratação (licitação) retornada pela API do PNCP.
    Mapeia o schema RecuperarCompraPublicacaoDTO da especificação OpenAPI.

    O campo numero_controle_pncp é a chave natural do domínio —
    usamos ele como ID tanto no Postgres quanto no Milvus para garantir
    que o join entre os dois stores seja simples e confiável.
    """
    numero_controle_pncp: str = Field(alias="numeroControlePNCP")
    objeto_compra: str = Field(alias="objetoCompra")
    modalidade_id: Optional[int] = Field(default=None, alias="modalidadeId")
    modalidade_nome: Optional[str] = Field(default=None, alias="modalidadeNome")
    modo_disputa_id: Optional[int] = Field(default=None, alias="modoDisputaId")
    modo_disputa_nome: Optional[str] = Field(default=None, alias="modoDisputaNome")
    valor_total_estimado: Optional[float] = Field(default=None, alias="valorTotalEstimado")
    valor_total_homologado: Optional[float] = Field(default=None, alias="valorTotalHomologado")
    situacao_compra_id: Optional[int] = Field(default=None, alias="situacaoCompraId")
    situacao_compra_nome: Optional[str] = Field(default=None, alias="situacaoCompraNome")
    data_publicacao_pncp: Optional[datetime] = Field(default=None, alias="dataPublicacaoPncp")
    data_abertura_proposta: Optional[datetime] = Field(default=None, alias="dataAberturaProposta")
    data_encerramento_proposta: Optional[datetime] = Field(default=None, alias="dataEncerramentoProposta")
    data_atualizacao: Optional[datetime] = Field(default=None, alias="dataAtualizacao")
    data_atualizacao_global: Optional[datetime] = Field(default=None, alias="dataAtualizacaoGlobal")
    orgao_entidade: Optional[OrgaoEntidade] = Field(default=None, alias="orgaoEntidade")
    unidade_orgao: Optional[UnidadeOrgao] = Field(default=None, alias="unidadeOrgao")
    srp: Optional[bool] = None  # Sistema de Registro de Preços
    link_sistema_origem: Optional[str] = Field(default=None, alias="linkSistemaOrigem")
    informacao_complementar: Optional[str] = Field(default=None, alias="informacaoComplementar")

    model_config = {"populate_by_name": True}

    @property
    def proposta_aberta(self) -> bool:
        """
        Propriedade derivada — calculada em tempo real para garantir precisão.
        Não armazenamos isso como campo fixo porque a janela de tempo muda constantemente.
        No Milvus, indexamos o datetime bruto e filtramos via expressão.
        """
        if self.data_encerramento_proposta is None:
            return False
        return self.data_encerramento_proposta > datetime.now(self.data_encerramento_proposta.tzinfo)

    @property
    def uf(self) -> Optional[str]:
        """Atalho para facilitar o acesso à UF nas camadas de persistência."""
        return self.unidade_orgao.uf_sigla if self.unidade_orgao else None

    @property
    def texto_para_embedding(self) -> str:
        """
        Campo que será transformado em vetor.
        Concatenamos objeto + informação complementar porque juntos
        oferecem o contexto semântico mais rico para busca por similaridade.
        """
        partes = [self.objeto_compra]
        if self.informacao_complementar:
            partes.append(self.informacao_complementar)
        return " ".join(partes)


class PaginaContratacoes(BaseModel):
    """Envelope de paginação retornado pela API do PNCP."""
    data: list[ContratacaoDTO] = Field(default_factory=list)
    total_registros: int = Field(alias="totalRegistros", default=0)
    total_paginas: int = Field(alias="totalPaginas", default=0)
    numero_pagina: int = Field(alias="numeroPagina", default=1)
    empty: bool = False

    model_config = {"populate_by_name": True}
