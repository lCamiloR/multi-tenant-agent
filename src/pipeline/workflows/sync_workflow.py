"""
Workflow de sincronização de licitações do PNCP.

Um Workflow no Temporal é uma função Python comum com uma propriedade
especial: ela é durável. Se o processo cair no meio da execução,
o Temporal recria o estado do Workflow a partir do histórico de eventos
e continua de onde parou — sem perda de progresso.

Como isso funciona internamente? O Temporal não "pausa" o processo —
ele grava cada evento (Activity iniciada, Activity completada, etc.)
em um log persistente. Ao reiniciar, ele "replay" esse log para
reconstituir o estado atual do Workflow. Por isso, código dentro de
um Workflow não pode ter efeitos colaterais não-determinísticos:
sem datetime.now() direto, sem random, sem I/O. Tudo isso vai para
as Activities.

Este Workflow itera sobre modalidades de contratação e, para cada uma,
pagina pela API do PNCP buscando registros atualizados nas últimas N horas.
Para cada item encontrado, gera embedding e persiste no Postgres + Milvus.
"""

from datetime import timedelta, datetime, timezone
from temporalio import workflow
from temporalio.common import RetryPolicy

# Importações de Activities são feitas via with_imports para evitar
# que o código das Activities seja executado durante o replay do Workflow.
with workflow.unsafe.imports_passed_through():
    from src.pipeline.activities.fetch_activity import fetch_contratacoes_page
    from src.pipeline.activities.upsert_activity import generate_embedding, upsert_licitacao
    from src.pipeline.models.state import FetchParams, SyncParams, UpsertParams


# Política de retry padrão para Activities de I/O externo (API PNCP, OpenAI).
# Backoff exponencial: tenta após 1s, 2s, 4s... até o máximo de 3 tentativas.
IO_RETRY_POLICY = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
)

# Retry mais conservador para persistência — falhas aqui podem indicar
# problemas mais sérios (banco fora do ar), então esperamos mais.
PERSIST_RETRY_POLICY = RetryPolicy(
    maximum_attempts=5,
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
)


@workflow.defn(name="SyncLicitacoesWorkflow")
class SyncLicitacoesWorkflow:
    """
    Orquestra a sincronização incremental de licitações do PNCP.

    O fluxo para cada modalidade é:
      1. Calcula o intervalo de tempo (agora - lookback_horas até agora)
      2. Busca a primeira página para descobrir o total de páginas
      3. Itera pelas páginas restantes
      4. Para cada item: gera embedding → persiste no Postgres + Milvus

    A escolha de processar modalidades sequencialmente (e não em paralelo)
    é conservadora em relação à API pública do PNCP — evitamos sobrecarga
    na fonte. Quando tiver rate limit documentado, pode paralelizar com
    workflow.gather() dentro dos limites permitidos.
    """

    @workflow.run
    async def run(self, params: SyncParams) -> dict:
        total_processados = 0
        total_erros = 0

        # workflow.now() é o equivalente seguro de datetime.now() dentro de um Workflow.
        # Usar datetime.now() quebraria o determinismo durante o replay.
        agora = workflow.now()
        data_fim = agora
        data_inicio = agora - timedelta(hours=params.lookback_horas)

        workflow.logger.info(
            f"Iniciando sync | modalidades={params.modalidades} "
            f"período={data_inicio.isoformat()} → {data_fim.isoformat()}"
        )

        for modalidade in params.modalidades:
            workflow.logger.info(f"Processando modalidade {modalidade}...")

            pagina = 1
            total_paginas = None  # descobrimos na primeira chamada

            while True:
                # Cada página é uma Activity independente com seu próprio retry.
                # Se a página 7 falhar 3 vezes, o Workflow inteiro falha —
                # mas o histórico mostra exatamente onde parou.
                fetch_result = await workflow.execute_activity(
                    fetch_contratacoes_page,
                    FetchParams(
                        data_inicio=data_inicio.isoformat(),
                        data_fim=data_fim.isoformat(),
                        modalidade=modalidade,
                        pagina=pagina,
                    ),
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=IO_RETRY_POLICY,
                )

                if fetch_result.empty:
                    workflow.logger.info(f"Modalidade {modalidade} | sem dados na página {pagina}.")
                    break

                if total_paginas is None:
                    total_paginas = fetch_result.total_paginas
                    workflow.logger.info(
                        f"Modalidade {modalidade} | total de páginas: {total_paginas}"
                    )

                # Processa cada item da página atual
                for item_json in fetch_result.items:
                    try:
                        # Passo 1: gera o embedding (chama a OpenAI)
                        embedding = await workflow.execute_activity(
                            generate_embedding,
                            item_json,
                            start_to_close_timeout=timedelta(seconds=30),
                            retry_policy=IO_RETRY_POLICY,
                        )

                        # Passo 2: persiste no Postgres e no Milvus
                        await workflow.execute_activity(
                            upsert_licitacao,
                            UpsertParams(item_json=item_json, embedding=embedding),
                            start_to_close_timeout=timedelta(seconds=30),
                            retry_policy=PERSIST_RETRY_POLICY,
                        )

                        total_processados += 1

                    except Exception as e:
                        # Logamos o erro mas não abortamos o workflow inteiro —
                        # um item com falha não deve impedir o processamento dos demais.
                        workflow.logger.error(f"Erro ao processar item: {e}")
                        total_erros += 1

                # Avança para a próxima página ou encerra o loop da modalidade
                if pagina >= (total_paginas or 1):
                    break
                pagina += 1

        resultado = {
            "total_processados": total_processados,
            "total_erros": total_erros,
            "modalidades": params.modalidades,
            "periodo_inicio": data_inicio.isoformat(),
            "periodo_fim": data_fim.isoformat(),
        }

        workflow.logger.info(f"Sync concluída | {resultado}")
        return resultado
