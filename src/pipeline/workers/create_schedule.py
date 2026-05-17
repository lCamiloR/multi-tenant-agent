"""
Script para criar o Schedule do Temporal que dispara o SyncLicitacoesWorkflow
automaticamente a cada intervalo configurado.

No Temporal, um Schedule é um objeto persistente no servidor — diferente de
um cron tradicional que vive apenas enquanto o processo está ativo. Se o
servidor Temporal reiniciar, o Schedule continua existindo e vai disparar
no próximo horário programado.

Este script é idempotente: se o Schedule já existir, ele atualiza a configuração.
Execute uma vez ao provisionar o ambiente — não precisa rodar a cada deploy.

Uso:
    python -m src.pipeline.workers.create_schedule
"""

import asyncio
import logging
from datetime import timedelta

from temporalio.client import Client, Schedule, ScheduleActionStartWorkflow
from temporalio.client import ScheduleSpec, ScheduleIntervalSpec, ScheduleState

from src.pipeline.workflows.sync_workflow import SyncLicitacoesWorkflow
from src.pipeline.models.state import SyncParams
from src.pipeline.workers.sync_worker import TASK_QUEUE
from src.core.config import SETTINGS

logger = logging.getLogger(__name__)

# ID único do Schedule no servidor Temporal.
# Use um nome descritivo — aparece no Temporal UI.
SCHEDULE_ID = "sync-licitacoes-pncp"

# Modalidades que o agente vai monitorar.
# 6 = Pregão Eletrônico (mais comum para TI e serviços)
# 8 = Dispensa Eletrônica (contratos menores, frequente em SaaS)
# Expanda conforme o domínio de negócio do seu cliente.
MODALIDADES_MONITORADAS = [6, 8]


async def create_or_update_schedule():
    client = await Client.connect(SETTINGS.temporal_host)

    params = SyncParams(
        modalidades=MODALIDADES_MONITORADAS,
        lookback_horas=2,  # busca as últimas 2 horas a cada execução
    )

    schedule = Schedule(
        action=ScheduleActionStartWorkflow(
            SyncLicitacoesWorkflow.run,
            params,
            id="sync-licitacoes-run",   # ID da instância de Workflow gerada
            task_queue=TASK_QUEUE,
        ),
        spec=ScheduleSpec(
            intervals=[
                # Roda a cada 1 hora, com lookback de 2 horas — isso garante
                # sobreposição de 1 hora entre execuções consecutivas,
                # evitando gaps se uma execução demorar mais que o esperado.
                ScheduleIntervalSpec(every=timedelta(hours=1))
            ]
        ),
        state=ScheduleState(
            note="Sincronização incremental de licitações do PNCP para Postgres + Milvus."
        ),
    )

    handle = client.get_schedule_handle(SCHEDULE_ID)

    try:
        await handle.describe()
        # Se chegou aqui, o Schedule já existe — atualiza a spec
        logger.info(f"Schedule '{SCHEDULE_ID}' já existe. Atualizando...")
        await handle.update(lambda _: schedule)
        logger.info("Schedule atualizado com sucesso.")
    except Exception:
        # Schedule não existe — cria
        logger.info(f"Criando schedule '{SCHEDULE_ID}'...")
        await client.create_schedule(SCHEDULE_ID, schedule)
        logger.info("Schedule criado com sucesso.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(create_or_update_schedule())
