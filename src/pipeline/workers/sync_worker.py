"""
Temporal worker for the procurement synchronization pipeline.

The Worker is the Python process that stays connected to the Temporal server,
waiting for tasks to execute. When the Temporal server has a Workflow or
Activity to run, it dispatches it to an available Worker in the correct queue
(task_queue).

Useful analogy: think of the Temporal server as a task manager,
and Workers as employees. The manager knows what needs to be done,
but employees have the tools to execute it.

To scale horizontally, simply run more instances of this worker —
Temporal automatically distributes the load among them.
"""

import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker

from src.pipeline.workflows.sync_workflow import SyncProcurementsWorkflow
from src.pipeline.activities.fetch_activity import fetch_procurements_page
from src.pipeline.activities.upsert_activity import generate_embeddings_batch, upsert_procurements_batch
from src.core.config import SETTINGS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Task queue name — Workflows and Workers must use the same name.
# In production, you can have separate queues by priority or job type.
TASK_QUEUE = "procurements-sync-queue"


async def run_worker():
    """
    Initializes the connection to the Temporal server and starts the Worker.

    The Worker is registered with the list of Workflows and Activities it
    is capable of executing. If the server tries to dispatch a task
    not registered here, the Worker will refuse — this is intentional,
    ensuring each Worker only executes what was explicitly declared.
    """
    logger.info(f"Connecting to Temporal at {SETTINGS.temporal_host}...")

    client = await Client.connect(SETTINGS.temporal_host)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SyncProcurementsWorkflow],
        activities=[
            fetch_procurements_page,
            generate_embeddings_batch,
            upsert_procurements_batch,
        ],
    ):
        logger.info(f"Worker active on queue '{TASK_QUEUE}'. Waiting for tasks...")
        # The Worker runs until the process is terminated (Ctrl+C or OS signal).
        # In production, this would be managed by Docker or a process manager.
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(run_worker())
