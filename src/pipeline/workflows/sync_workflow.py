import asyncio
from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.pipeline.activities.fetch_activity import fetch_procurements_page
    from src.pipeline.activities.upsert_activity import (
        generate_embeddings_batch,
        upsert_procurements_batch,
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


@workflow.defn(name="SyncProcurementsWorkflow")
class SyncProcurementsWorkflow:

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
            f"Execution started | remaining_modalities={progress.remaining_modalities} "
            f"resume_page={progress.current_page} "
            f"period={progress.start_date} → {progress.end_date}"
        )

        pages_this_execution = 0

        while progress.remaining_modalities:
            modality = progress.remaining_modalities[0]
            total_pages = None
            page = progress.current_page

            while True:
                fetch_result = await workflow.execute_activity(
                    fetch_procurements_page,
                    FetchParams(
                        start_date=progress.start_date,
                        end_date=progress.end_date,
                        modality=modality,
                        page=page,
                    ),
                    start_to_close_timeout=timedelta(seconds=120),
                    retry_policy=IO_RETRY_POLICY,
                )

                if fetch_result.empty:
                    workflow.logger.info(
                        f"Modality {modality} | no data on page {page} — done."
                    )
                    break

                if total_pages is None:
                    total_pages = fetch_result.total_pages
                    workflow.logger.info(
                        f"Modality {modality} | total pages: {total_pages}"
                    )

                try:
                    embeddings = await workflow.execute_activity(
                        generate_embeddings_batch,
                        BatchEmbeddingParams(items_json=fetch_result.items),
                        start_to_close_timeout=timedelta(seconds=120),
                        retry_policy=IO_RETRY_POLICY,
                    )

                    processed = await workflow.execute_activity(
                        upsert_procurements_batch,
                        BatchUpsertParams(
                            items_json=fetch_result.items,
                            embeddings=embeddings,
                        ),
                        start_to_close_timeout=timedelta(seconds=120),
                        retry_policy=PERSIST_RETRY_POLICY,
                    )

                    progress.total_processed += processed
                    pages_this_execution += 1

                except Exception as e:
                    workflow.logger.error(
                        f"Error on modality {modality} page {page}: {e}"
                    )
                    progress.total_errors += 1

                # ── continue_as_new checkpoint ──────────────────────────────
                # After PAGES_PER_EXECUTION pages, hand off to a fresh execution
                # carrying the current progress forward. The new execution will
                # resume from the next page of the current modality.
                if pages_this_execution >= PAGES_PER_EXECUTION:
                    next_page = page + 1
                    resume = SyncProgress(
                        remaining_modalities=progress.remaining_modalities,
                        current_page=next_page,
                        start_date=progress.start_date,
                        end_date=progress.end_date,
                        total_processed=progress.total_processed,
                        total_errors=progress.total_errors,
                        lookback_hours=progress.lookback_hours,
                    )
                    workflow.logger.info(
                        f"History checkpoint reached | continuing as new "
                        f"from modality={modality} page={next_page}"
                    )
                    workflow.continue_as_new(resume)

                await asyncio.sleep(0.5)

                if page >= (total_pages or 1):
                    break

                page += 1

            # Current modality is done — advance to the next one,
            # resetting the page counter for the fresh modality.
            progress.remaining_modalities = progress.remaining_modalities[1:]
            progress.current_page = 1

        result = {
            "total_processed": progress.total_processed,
            "total_errors": progress.total_errors,
            "period_start": progress.start_date,
            "period_end": progress.end_date,
        }

        workflow.logger.info(f"Sync complete | {result}")
        return result

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

        now = workflow.now()
        return SyncProgress(
            remaining_modalities=params.modalities,
            current_page=1,
            start_date=(now - timedelta(hours=params.lookback_hours)).isoformat(),
            end_date=now.isoformat(),
            lookback_hours=params.lookback_hours,
        )
