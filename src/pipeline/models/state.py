"""
Internal state models for the Temporal pipeline.

In Temporal, everything passed between Workflows and Activities must be
serializable. Temporal uses JSON by default, so Pydantic is the natural choice —
it serializes/deserializes automatically and validates data.

We intentionally separate these models from the API DTOs (pncp.py):
the DTOs represent the contract with the external source, while these
models represent the internal state of our orchestration.
"""

from dataclasses import dataclass


@dataclass
class FetchParams:
    """
    Parameters passed to the Activity that fetches a page from the API.

    We use dataclass instead of Pydantic here because Temporal
    has native dataclass support for serialization — it is lighter
    for objects that are only data containers without validation logic.
    """
    start_date: str
    end_date: str
    modality: int
    page: int = 1
    page_size: int = 50


@dataclass
class PageResult:
    """
    Result of a fetch Activity — encapsulates what came from a single page.
    The workflow uses total_pages to decide whether to continue paginating.
    """
    items: list
    total_pages: int
    current_page: int
    empty: bool


@dataclass
class SyncParams:
    """
    Input parameters for the main Workflow.
    The Temporal Schedule injects this on each execution.

    modalities is the list of codes the workflow will iterate —
    one at a time, to avoid overloading the API. Common values:
      1 = Electronic Auction
      2 = Competitive Dialogue
      3 = Contest
      4 = Electronic Open Bidding
      5 = In-person Open Bidding
      6 = Electronic Pregao  ← most common for IT
      7 = In-person Pregao
      8 = Electronic Waiver
    """
    modalities: list[int]
    lookback_hours: int = 2


@dataclass
class BatchUpsertParams:
    """
    Parameters for upsert_procurements_batch.
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
        remaining_modalities: modalities not yet fully processed.
        current_page: the page to resume from within the current modality.
        start_date / end_date: fixed at Workflow start so that all
            continued executions query the same time window.
        total_processed / total_errors: accumulated counters carried forward.
        lookback_hours: preserved for logging/observability.
    """
    remaining_modalities: list[int]
    current_page: int
    start_date: str
    end_date: str
    total_processed: int = 0
    total_errors: int = 0
    lookback_hours: int = 2
