"""
Activity responsible for fetching a page of procurements from the PNCP API.

In Temporal's model, an Activity is the smallest unit of work with
its own retry policy. The decision to create one Activity per page (rather than
fetching all pages in a single Activity) is strategic:

- If page 7 of 20 fails, Temporal retries ONLY that page.
  With everything in one Activity, a failure on page 7 would discard the work
  from pages 1–6 and start from scratch.

- The execution history in the Temporal UI is granular — you can see
  exactly which page failed and why.

- The timeout per Activity can be calibrated for a single page (30s),
  not for the full fetch (minutes).
"""

from datetime import datetime
from temporalio import activity
from src.pipeline.clients.pncp_client import PNCPClient
from src.pipeline.models.state import FetchParams, PageResult

import logging

logger = logging.getLogger(__name__)


@activity.defn(name="fetch_procurements_page")
async def fetch_procurements_page(params: FetchParams) -> PageResult:
    """
    Fetches a single page of updated procurements from PNCP.

    The @activity.defn decorator registers this function as an Activity
    recognized by the Temporal worker. The 'name' parameter is the
    identifier the Workflow uses to dispatch the task — if you rename the
    Python function, the Workflow continues working as long as the 'name' is kept.
    """
    client = PNCPClient()

    try:
        # Converts ISO strings back to datetime for the HTTP client
        start_date = datetime.fromisoformat(params.start_date)
        end_date = datetime.fromisoformat(params.end_date)

        page_result = await client.get_updated_procurements(
            start_date=start_date,
            end_date=end_date,
            modality=params.modality,
            page=params.page,
            page_size=params.page_size,
        )

        logger.info(
            f"Page {params.page}/{page_result.total_pages} | "
            f"modality={params.modality} | "
            f"items={len(page_result.data)}"
        )

        return PageResult(
            # We serialize items as JSON because Temporal needs to
            # serialize the Activity return value, and ProcurementDTO is Pydantic —
            # we use model_dump_json() for clean serialization.
            items=[item.model_dump_json(by_alias=False) for item in page_result.data],
            total_pages=page_result.total_pages,
            current_page=page_result.page_number,
            empty=page_result.empty or len(page_result.data) == 0,
        )

    finally:
        # Always close the HTTP client at the end of the Activity to avoid
        # connection leaks — each Activity has its own lifecycle.
        await client.close()
