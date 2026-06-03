"""
Worker do Temporal para o pipeline de sincronização de licitações.

O Worker é o processo Python que fica conectado ao servidor Temporal,
aguardando tarefas para executar. Quando o servidor Temporal tem um
Workflow ou Activity para rodar, ele despacha para um Worker disponível
na fila correta (task_queue).

Analogia útil: pense no servidor Temporal como um gerente de tarefas,
e nos Workers como funcionários. O gerente sabe o que precisa ser feito,
mas são os funcionários que têm as ferramentas para executar.

Para escalar horizontalmente, basta rodar mais instâncias deste worker —
o Temporal distribui automaticamente a carga entre eles.
"""

import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker

from src.pipeline.workflows.sync_workflow import SyncLicitacoesWorkflow
from src.pipeline.activities.fetch_activity import fetch_contratacoes_page
from src.pipeline.activities.upsert_activity import generate_embeddings_batch, upsert_licitacoes_batch
from src.core.config import SETTINGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Nome da fila de tarefas — Workflows e Workers precisam usar o mesmo nome.
# Em produção, você pode ter filas separadas por prioridade ou tipo de job.
TASK_QUEUE = "licitacoes-sync-queue"


async def run_worker():
    """
    Inicializa a conexão com o servidor Temporal e sobe o Worker.

    O Worker é registrado com a lista de Workflows e Activities que
    ele é capaz de executar. Se o servidor tentar despachar uma tarefa
    que não está registrada aqui, o Worker vai recusar — isso é intencional,
    garante que cada Worker só executa o que foi explicitamente declarado.
    """
    logger.info(f"Conectando ao Temporal em {SETTINGS.temporal_host}...")

    client = await Client.connect(SETTINGS.temporal_host)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SyncLicitacoesWorkflow],
        activities=[
            fetch_contratacoes_page,
            generate_embeddings_batch,
            upsert_licitacoes_batch,
        ],
    ):
        logger.info(f"Worker ativo na fila '{TASK_QUEUE}'. Aguardando tarefas...")
        # O Worker roda até o processo ser encerrado (Ctrl+C ou sinal do SO).
        # Em produção, isso seria gerenciado pelo Docker ou por um process manager.
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(run_worker())
