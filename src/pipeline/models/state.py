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
from datetime import datetime
from typing import Optional


@dataclass
class FetchParams:
    """
    Parâmetros passados para a Activity que busca uma página da API.

    Usamos dataclass em vez de Pydantic aqui porque o Temporal
    tem suporte nativo a dataclasses para serialização — é mais leve
    para objetos que são só contêineres de dados sem lógica de validação.
    """
    data_inicio: str          # formato ISO: "20250101000000" — exigido pela API do PNCP
    data_fim: str
    modalidade: int           # código da modalidade de contratação (obrigatório na API)
    pagina: int = 1
    tamanho_pagina: int = 50


@dataclass
class PageResult:
    """
    Resultado de uma Activity de fetch — encapsula o que veio de uma página.
    O workflow usa total_paginas para decidir se deve continuar paginando.
    """
    items: list               # lista de ContratacaoDTO (tipagem genérica p/ serialização)
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
    lookback_horas: int = 2   # quantas horas para trás buscar atualizações


@dataclass
class BatchUpsertParams:
    """
    Parâmetros para a Activity de persistência.
    Encapsula tanto os dados da contratação quanto o vetor gerado
    para que a Activity de upsert seja atômica — ou persiste tudo, ou nada.
    """
    items_json: list[str]
    embeddings: list[list[float]]
