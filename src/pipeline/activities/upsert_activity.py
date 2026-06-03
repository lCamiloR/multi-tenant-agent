# src/pipeline/activities/upsert_activity.py

import logging
from temporalio import activity

from src.pipeline.clients.milvus_client import MilvusLicitacoesClient
from src.pipeline.clients.embedding_client import EmbeddingClient
from src.pipeline.models.pncp import ContratacaoDTO
from src.pipeline.models.state import BatchUpsertParams, BatchEmbeddingParams
from src.pipeline.mappers.pncp_mapper import to_procurement, to_procuring_entity
from src.db.repositories.procuring_entity_repo import ProcuringEntityRepository
from src.db.repositories.procurement_repo import ProcurementRepository
from src.db.session import get_session_ctx
from src.core.config import SETTINGS

logger = logging.getLogger(__name__)


@activity.defn(name="generate_embeddings_batch")
async def generate_embeddings_batch(params: BatchEmbeddingParams) -> list[list[float]]:
    """
    Generates embeddings for all items in a page in a single batched API call.

    Batching is intentional: instead of N round-trips to OpenAI (one per item),
    we make a single request. This reduces latency and cost significantly.

    Keeping this as a separate activity from upsert preserves the original
    design principle: each activity has a single, well-defined responsibility
    and its own independent retry policy.
    """
    embedder = EmbeddingClient(api_key=SETTINGS.openai_api_key)

    items = [ContratacaoDTO.model_validate_json(j) for j in params.items_json]
    texts = [item.texto_para_embedding for item in items]

    logger.info(f"Generating embeddings | batch_size={len(texts)}")
    return await embedder.embed_batch(texts)


@activity.defn(name="upsert_licitacoes_batch")
async def upsert_licitacoes_batch(params: BatchUpsertParams) -> int:
    """
    Persists a full page of procurements into Postgres and Milvus.

    Receives pre-computed embeddings — this activity is responsible
    exclusively for persistence, not for calling any external AI APIs.

    Both stores are idempotent:
      - Postgres: INSERT ... ON CONFLICT DO UPDATE (keyed on pncp_control_number)
      - Milvus: upsert by primary id (numeroControlePNCP)

    This means retrying this activity on failure is always safe.

    Returns the count of successfully persisted items.
    """
    items = [ContratacaoDTO.model_validate_json(j) for j in params.items_json]

    async with get_session_ctx() as session:
        procuring_entity_repo = ProcuringEntityRepository(session)
        procurement_repo = ProcurementRepository(session)

        for item in items:
            logger.info(f"[Postgres] Upsert | id={item.numero_controle_pncp}")
            entity = to_procuring_entity(item)
            saved_entity = await procuring_entity_repo.upsert(entity)
            procurement = to_procurement(item, saved_entity.id)
            await procurement_repo.upsert(procurement)

        await session.commit()

    milvus = MilvusLicitacoesClient(uri=SETTINGS.milvus_uri)
    try:
        milvus.upsert_batch(
            items_json=params.items_json,
            embeddings=params.embeddings,
        )
        logger.info(f"[Milvus] Batch upsert | {len(items)} items")
    finally:
        milvus.close()

    return len(items)