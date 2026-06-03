"""
Modelos de estado interno do pipeline Temporal.

No Temporal, tudo que é passado entre Workflows e Activities precisa ser
serializável. O Temporal usa JSON por padrão, então Pydantic é a escolha
natural — serializa/deserializa automaticamente e valida os dados.

Separamos esses modelos dos DTOs da API (pncp.py) intencionalmente:
os DTOs representam o contrato com a fonte externa, enquanto estes
modelos representam o estado interno da nossa orquestração.
"""

from dataclasses import dataclass


@dataclass
class FetchParams:
    """
    Parâmetros passados para a Activity que busca uma página da API.

    Usamos dataclass em vez de Pydantic aqui porque o Temporal
    tem suporte nativo a dataclasses para serialização — é mais leve
    para objetos que são só contêineres de dados sem lógica de validação.
    """
    data_inicio: str
    data_fim: str
    modalidade: int
    pagina: int = 1
    tamanho_pagina: int = 50


@dataclass
class PageResult:
    """
    Resultado de uma Activity de fetch — encapsula o que veio de uma página.
    O workflow usa total_paginas para decidir se deve continuar paginando.
    """
    items: list
    total_paginas: int
    pagina_atual: int
    empty: bool


@dataclass
class SyncParams:
    """
    Parâmetros de entrada do Workflow principal.
    O Schedule do Temporal injeta isso a cada execução.

    modalidades é a lista de códigos que o workflow vai iterar —
    um por vez, para não sobrecarregar a API. Valores comuns:
      1 = Leilão Eletrônico
      2 = Diálogo Competitivo
      3 = Concurso
      4 = Concorrência Eletrônica
      5 = Concorrência Presencial
      6 = Pregão Eletrônico  ← mais comum para TI
      7 = Pregão Presencial
      8 = Dispensa Eletrônica
    """
    modalidades: list[int]
    lookback_horas: int = 2


@dataclass
class BatchUpsertParams:
    """
    Parameters for upsert_licitacoes_batch.
    Embeddings are generated upstream (by generate_embeddings_batch activity)
    and passed here — this activity is responsible only for persistence.
    """
    items_json: list[str]
    embeddings: list[list[float]]


@dataclass
class BatchEmbeddingParams:
    """
    Parameters for generate_embeddings_batch.
    Groups all items from a page into a single activity call,
    keeping responsibilities clean: one activity generates, one persists.
    """
    items_json: list[str]


@dataclass
class SyncProgress:
    """
    Carries execution state across continue_as_new boundaries.

    When the Workflow history approaches the size limit, the current
    Workflow calls continue_as_new(SyncProgress(...)) and a fresh
    execution resumes exactly where the previous one left off.

    Fields:
        modalidades_restantes: modalities not yet fully processed.
        pagina_atual: the page to resume from within the current modality.
        data_inicio / data_fim: fixed at Workflow start so that all
            continued executions query the same time window.
        total_processados / total_erros: accumulated counters carried forward.
        lookback_horas: preserved for logging/observability.
    """
    modalidades_restantes: list[int]
    pagina_atual: int
    data_inicio: str
    data_fim: str
    total_processados: int = 0
    total_erros: int = 0
    lookback_horas: int = 2