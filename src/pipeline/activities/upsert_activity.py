"""
Activity responsável por persistir uma contratação no Postgres e no Milvus.

Esta é a Activity mais crítica do pipeline porque ela coordena duas
escritas em stores diferentes. É importante entender o que isso implica:
não temos transação distribuída aqui — se o upsert no Postgres funcionar
mas o Milvus falhar, o Temporal vai reexecutar a Activity inteira.

Isso significa que o upsert no Postgres precisa ser idempotente.
A chave natural (numero_controle_pncp) garante isso via INSERT ... ON CONFLICT.
O Milvus também é idempotente por design — upsert com o mesmo ID substitui.

Esse padrão é chamado de "at-least-once delivery" — preferimos processar
um item mais de uma vez do que perdê-lo. Com idempotência nos dois stores,
reprocessamentos são seguros.
"""

import logging
from temporalio import activity

from src.pipeline.clients.milvus_client import MilvusLicitacoesClient
from src.pipeline.clients.embedding_client import EmbeddingClient
from src.pipeline.models.pncp import ContratacaoDTO
from src.pipeline.models.state import BatchUpsertParams
from src.pipeline.mappers.pncp_mapper import to_procurement, to_procuring_entity
from src.db.repositories.procuring_entity_repo import ProcuringEntityRepository
from src.db.repositories.procurement_repo import ProcurementRepository
from src.db.session import get_session_ctx
from src.core.config import SETTINGS

logger = logging.getLogger(__name__)


@activity.defn(name="generate_embedding")
async def generate_embedding(item_json: str) -> list[float]:
    """
    Gera o embedding para o texto de uma contratação.

    Separamos a geração de embedding do upsert em Activities distintas
    por duas razões:
    1. A chamada à OpenAI é I/O bound e pode ter latência variável —
       ter retry independente evita reprocessar o upsert por falha de rede.
    2. Em versões futuras, podemos paralelizar a geração de embeddings
       com workflow.gather() antes de persistir em batch.
    """
    embedder = EmbeddingClient(api_key=SETTINGS.openai_api_key)

    item = ContratacaoDTO.model_validate_json(item_json)
    texto = item.texto_para_embedding

    logger.debug(f"Gerando embedding | id={item.numero_controle_pncp} | chars={len(texto)}")

    return await embedder.embed(texto)


@activity.defn(name="upsert_licitacoes_batch")
async def upsert_licitacoes_batch(params: BatchUpsertParams) -> None:
    """
    Persiste a contratação no Postgres e no Milvus de forma idempotente.

    A ordem importa: persistimos no Postgres primeiro porque é a nossa
    fonte de verdade (dados completos). O Milvus é um índice de busca —
    se ele estiver desatualizado momentaneamente, o agente pode não
    encontrar o item em busca semântica, mas os dados não se perdem.
    O caminho inverso (Milvus com ID que não existe no Postgres) criaria
    resultados de busca que não podem ser hidratados — pior situação.
    """
    items = [ContratacaoDTO.model_validate_json(j) for j in params.items_json]

    # --- Postgres: single transaction for the whole page ---
    async with get_session_ctx() as session:
        procuring_entity_repo = ProcuringEntityRepository(session)
        procurement_repo = ProcurementRepository(session)

        for item in items:
            logger.info(f"[Postgres] Upsert | id={item.numero_controle_pncp}")
            entity = to_procuring_entity(item)
            saved_entity = await procuring_entity_repo.upsert(entity)
            
            procurement = to_procurement(item, saved_entity.id)
            await procurement_repo.upsert(procurement)
        
        # Single commit for all items in the page
        await session.commit()

    # --- Milvus: batch insert ---
    milvus = MilvusLicitacoesClient(uri=SETTINGS.milvus_uri)
    try:
        milvus.upsert_batch(
            items_json=params.items_json,
            embeddings=params.embeddings
        )
    finally:
        milvus.close()
