import asyncio
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.pipeline.activities.fetch_activity import fetch_contratacoes_page
    from src.pipeline.activities.upsert_activity import (
        generate_embeddings_batch,
        upsert_licitacoes_batch,
    )
    from src.pipeline.models.state import (
        FetchParams,
        SyncParams,
        SyncProgress,
        BatchEmbeddingParams,
        BatchUpsertParams,
    )


IO_RETRY_POLICY = RetryPolicy(
    maximum_attempts=5,
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=30),
)

PERSIST_RETRY_POLICY = RetryPolicy(
    maximum_attempts=5,
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
)

PAGES_PER_EXECUTION = 5


@workflow.defn(name="SyncLicitacoesWorkflow")
class SyncLicitacoesWorkflow:

    @workflow.run
    async def run(self, params: SyncParams | SyncProgress) -> dict:
        """
        Entry point — accepts either SyncParams (first run, triggered by Schedule)
        or SyncProgress (resumed run, triggered by continue_as_new).

        This dual-input pattern is the standard Temporal approach for workflows
        that may need to continue themselves: the Schedule always sends SyncParams,
        while continued executions receive SyncProgress with accumulated state.
        """
        progress = self._init_progress(params)

        workflow.logger.info(
            f"Execution started | modalities_remaining={progress.modalidades_restantes} "
            f"resume_page={progress.pagina_atual} "
            f"period={progress.data_inicio} → {progress.data_fim}"
        )

        pages_this_execution = 0

        while progress.modalidades_restantes:
            modalidade = progress.modalidades_restantes[0]
            total_paginas = None
            pagina = progress.pagina_atual

            while True:
                fetch_result = await workflow.execute_activity(
                    fetch_contratacoes_page,
                    FetchParams(
                        data_inicio=progress.data_inicio,
                        data_fim=progress.data_fim,
                        modalidade=modalidade,
                        pagina=pagina,
                    ),
                    start_to_close_timeout=timedelta(seconds=120),
                    retry_policy=IO_RETRY_POLICY,
                )

                if fetch_result.empty:
                    workflow.logger.info(
                        f"Modality {modalidade} | no data on page {pagina} — done."
                    )
                    break

                if total_paginas is None:
                    total_paginas = fetch_result.total_paginas
                    workflow.logger.info(
                        f"Modality {modalidade} | total pages: {total_paginas}"
                    )

                try:
                    embeddings = await workflow.execute_activity(
                        generate_embeddings_batch,
                        BatchEmbeddingParams(items_json=fetch_result.items),
                        start_to_close_timeout=timedelta(seconds=120),
                        retry_policy=IO_RETRY_POLICY,
                    )

                    processed = await workflow.execute_activity(
                        upsert_licitacoes_batch,
                        BatchUpsertParams(
                            items_json=fetch_result.items,
                            embeddings=embeddings,
                        ),
                        start_to_close_timeout=timedelta(seconds=120),
                        retry_policy=PERSIST_RETRY_POLICY,
                    )

                    progress.total_processados += processed
                    pages_this_execution += 1

                except Exception as e:
                    workflow.logger.error(
                        f"Error on modality {modalidade} page {pagina}: {e}"
                    )
                    progress.total_erros += 1

                # ── continue_as_new checkpoint ──────────────────────────────
                # After PAGES_PER_EXECUTION pages, hand off to a fresh execution
                # carrying the current progress forward. The new execution will
                # resume from the next page of the current modality.
                if pages_this_execution >= PAGES_PER_EXECUTION:
                    next_page = pagina + 1
                    resume = SyncProgress(
                        modalidades_restantes=progress.modalidades_restantes,
                        pagina_atual=next_page,
                        data_inicio=progress.data_inicio,
                        data_fim=progress.data_fim,
                        total_processados=progress.total_processados,
                        total_erros=progress.total_erros,
                        lookback_horas=progress.lookback_horas,
                    )
                    workflow.logger.info(
                        f"History checkpoint reached | continuing as new "
                        f"from modality={modalidade} page={next_page}"
                    )
                    workflow.continue_as_new(resume)

                await asyncio.sleep(0.5)

                if pagina >= (total_paginas or 1):
                    break

                pagina += 1

            # Current modality is done — advance to the next one,
            # resetting the page counter for the fresh modality.
            progress.modalidades_restantes = progress.modalidades_restantes[1:]
            progress.pagina_atual = 1

        resultado = {
            "total_processados": progress.total_processados,
            "total_erros": progress.total_erros,
            "periodo_inicio": progress.data_inicio,
            "periodo_fim": progress.data_fim,
        }

        workflow.logger.info(f"Sync complete | {resultado}")
        return resultado

    def _init_progress(self, params: SyncParams | SyncProgress) -> SyncProgress:
        """
        Normalizes the two possible input types into a single SyncProgress.

        On the first run (SyncParams from Schedule): computes the time window
        and initializes counters from zero.

        On resumed runs (SyncProgress from continue_as_new): passes through
        the existing progress unchanged — time window and counters are preserved.
        """
        if isinstance(params, SyncProgress):
            return params

        agora = workflow.now()
        return SyncProgress(
            modalidades_restantes=params.modalidades,
            pagina_atual=1,
            data_inicio=(agora - timedelta(hours=params.lookback_horas)).isoformat(),
            data_fim=agora.isoformat(),
            lookback_horas=params.lookback_horas,
        )