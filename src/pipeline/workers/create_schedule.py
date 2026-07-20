"""
Script to create the Temporal Schedule that triggers SyncProcurementsWorkflow
automatically at each configured interval.

In Temporal, a Schedule is a persistent object on the server — unlike a
traditional cron that only lives while the process is active. If the
Temporal server restarts, the Schedule continues to exist and will fire
at the next scheduled time.

This script is idempotent: if the Schedule already exists, it updates the configuration.
Run once when provisioning the environment — no need to run on every deploy.

Usage:
    python -m src.pipeline.workers.create_schedule
"""

import asyncio
import logging
from datetime import timedelta

from temporalio.client import Client, Schedule, ScheduleActionStartWorkflow
from temporalio.client import ScheduleSpec, ScheduleIntervalSpec, ScheduleState

from src.pipeline.workflows.sync_workflow import SyncProcurementsWorkflow
from src.pipeline.models.state import SyncParams
from src.pipeline.workers.sync_worker import TASK_QUEUE
from src.core.config import SETTINGS

logger = logging.getLogger(__name__)

# Unique Schedule ID on the Temporal server.
# Use a descriptive name — it appears in the Temporal UI.
SCHEDULE_ID = "sync-procurements-pncp"

# Modalities the agent will monitor.
# 6 = Electronic Pregao (most common for IT and services)
# 8 = Electronic Waiver (smaller contracts, frequent in SaaS)
# Expand according to your client's business domain.
MONITORED_MODALITIES = [6, 8]


async def create_or_update_schedule():
    client = await Client.connect(SETTINGS.temporal_host)

    params = SyncParams(
        modalities=MONITORED_MODALITIES,
        lookback_hours=2,  # fetches the last 2 hours on each execution
    )

    schedule = Schedule(
        action=ScheduleActionStartWorkflow(
            SyncProcurementsWorkflow.run,
            params,
            id="sync-procurements-run",   # ID of the generated Workflow instance
            task_queue=TASK_QUEUE,
        ),
        spec=ScheduleSpec(
            intervals=[
                # Runs every 1 hour, with a 2-hour lookback — this ensures
                # 1-hour overlap between consecutive executions,
                # preventing gaps if an execution takes longer than expected.
                ScheduleIntervalSpec(every=timedelta(hours=1))
            ]
        ),
        state=ScheduleState(
            note="Incremental synchronization of PNCP procurements to Postgres + Milvus."
        ),
    )

    handle = client.get_schedule_handle(SCHEDULE_ID)

    try:
        await handle.describe()
        # If we get here, the Schedule already exists — update the spec
        logger.info(f"Schedule '{SCHEDULE_ID}' already exists. Updating...")
        await handle.update(lambda _: schedule)
        logger.info("Schedule updated successfully.")
    except Exception:
        # Schedule does not exist — create it
        logger.info(f"Creating schedule '{SCHEDULE_ID}'...")
        await client.create_schedule(SCHEDULE_ID, schedule)
        logger.info("Schedule created successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(create_or_update_schedule())
