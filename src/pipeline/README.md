# Pipeline — Sync de Licitações (PNCP → Postgres + Milvus)

This pipeline synchronizes Brazilian government procurement data from the [PNCP API](https://pncp.gov.br/api/consulta) into two stores in parallel:

- **PostgreSQL** — structured source of truth (full procurement records)
- **Milvus** — vector index for semantic search (embeddings of procurement objects)

Orchestration is handled by **Temporal**, which provides durable execution, automatic retries, and scheduling out of the box.

---

## Architecture Overview

```
PNCP API
    │
    ▼
fetch_contratacoes_page (Activity)
    │  one Activity per page — granular retries
    ▼
generate_embedding (Activity)
    │  calls OpenAI text-embedding-3-small
    ▼
upsert_licitacao (Activity)
    ├── PostgreSQL  (procuring_entity → procurement, idempotent via ON CONFLICT)
    └── Milvus      (vector upsert by pncp_control_number)
```

The `SyncLicitacoesWorkflow` orchestrates all of the above. It iterates over configured procurement modalities, paginates the PNCP API, and dispatches one set of Activities per item found. A **Temporal Schedule** triggers the workflow automatically every hour.

---

## Prerequisites

All infrastructure services run via Docker Compose. The Python worker runs locally (outside Docker) and connects to them via `localhost`.

Make sure you have installed:

- Docker and Docker Compose
- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/) (recommended) or `pip`

---

## Step 1 — Configure environment variables

Copy the example file and fill in the required values:

```bash
cp .env.example .env
```

Open `.env` and set at minimum:

```env
PRIMARY_JWT_SECRET_KEY=any-long-random-string-for-dev
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...          # Required — used by EmbeddingClient to call text-embedding-3-small
```

The following variables have working defaults for local development and only need to be set if you want to override them:

```env
MILVUS_URI=http://localhost:19530
TEMPORAL_HOST=localhost:7233
DATABASE_URL=postgresql+asyncpg://postgres:secret@localhost:5432/multi_tenant_agent
```

---

## Step 2 — Start infrastructure services

```bash
docker compose up -d
```

This starts Postgres, Milvus (with its etcd and MinIO dependencies), Temporal, and the Temporal UI. Wait until all services are healthy before proceeding:

```bash
docker compose ps
```

All services should show `healthy` status. The Milvus stack takes the longest — etcd and MinIO must pass their healthchecks before Milvus itself starts. If any service shows `starting` after ~2 minutes, inspect its logs:

```bash
docker compose logs milvus --tail 30
```

**Services and their ports:**

| Service      | Port  | Purpose                          |
|--------------|-------|----------------------------------|
| Postgres     | 5432  | Structured data store            |
| Milvus       | 19530 | Vector store (gRPC)              |
| Temporal     | 7233  | Workflow orchestration server    |
| Temporal UI  | 8080  | Execution monitoring dashboard   |

---

## Step 3 — Install Python dependencies

```bash
# With uv (recommended)
uv sync

# Or with pip
pip install -e .
```

---

## Step 4 — Apply database migrations

The schema is managed by Alembic. If you are running the pipeline for the first time, generate and apply the initial migration:

```bash
# Generate the migration by inspecting the SQLAlchemy models
alembic revision --autogenerate -m "initial schema"

# Review the generated file in migrations/versions/ before applying
# Then apply:
alembic upgrade head
```

If the schema already exists and is up to date, just run:

```bash
alembic upgrade head
```

To verify the tables were created correctly:

```bash
docker exec -it multi-tenant-agent-postgres-1 \
  psql -U postgres -d multi_tenant_agent -c "\dt"
```

Expected output:

```
           List of relations
 Schema |      Name        | Type  |  Owner
--------+------------------+-------+----------
 public | alembic_version  | table | postgres
 public | procurement      | table | postgres
 public | procuring_entity | table | postgres
```

---

## Step 5 — Start the Temporal worker

The worker is the Python process that connects to the Temporal server and executes Workflows and Activities. It must be running for any sync to happen.

Open a dedicated terminal and run:

```bash
python -m src.pipeline.workers.sync_worker
```

You should see:

```
INFO  Conectando ao Temporal em localhost:7233...
INFO  Worker ativo na fila 'licitacoes-sync-queue'. Aguardando tarefas...
```

Keep this terminal open. The worker runs until interrupted with `Ctrl+C`.

---

## Step 6 — Create the sync schedule

The schedule tells Temporal to trigger `SyncLicitacoesWorkflow` automatically every hour. This script is **idempotent** — run it once to provision, and re-run it anytime to update the configuration.

Open a second terminal and run:

```bash
python -m src.pipeline.workers.create_schedule
```

Expected output:

```
INFO  Criando schedule 'sync-licitacoes-pncp'...
INFO  Schedule criado com sucesso.
```

After this, Temporal will immediately trigger the first run and then repeat every hour. You can inspect the schedule and its execution history in the Temporal UI at [http://localhost:8080](http://localhost:8080).

---

## Monitoring execution

### Temporal UI

Open [http://localhost:8080](http://localhost:8080) to see:

- Active and completed Workflow executions
- Individual Activity results and retry history
- The Schedule and its next scheduled run

### Worker logs

The terminal running `sync_worker` outputs one log line per page fetched and per item upserted:

```
INFO  Página 1/4 | modalidade=6 | itens=50
INFO  [Postgres] Upsert | id=00010.492165/0001-09-2025-000001/1
INFO  [Milvus]   Upsert | id=00010.492165/0001-09-2025-000001/1
```

### Verify data in Postgres

```bash
cat > /tmp/check_data.py << 'EOF'
import asyncio
from sqlalchemy import text
from src.db.session import engine

async def check():
    async with engine.connect() as conn:
        pe = await conn.execute(text("SELECT COUNT(*) FROM procuring_entity"))
        p  = await conn.execute(text("SELECT COUNT(*) FROM procurement"))
        print(f"procuring_entity rows : {pe.scalar()}")
        print(f"procurement rows      : {p.scalar()}")

asyncio.run(check())
EOF

python /tmp/check_data.py
```

---

## Modalities monitored

Modalities are configured in `src/pipeline/workers/create_schedule.py`:

```python
MODALIDADES_MONITORADAS = [6, 8]
```

| Code | Description                        |
|------|------------------------------------|
| 6    | Pregão Eletrônico (most common for IT and services) |
| 8    | Dispensa Eletrônica (smaller contracts)             |

To monitor additional modalities, add their codes to the list and re-run `create_schedule.py`. The full list of modality codes is documented in `src/pipeline/models/state.py`.

---

## Running a one-off sync manually

If you need to trigger a sync outside the hourly schedule — for example, to backfill a larger time window — you can start a Workflow execution directly:

```bash
cat > /tmp/manual_sync.py << 'EOF'
import asyncio
from temporalio.client import Client
from src.pipeline.workflows.sync_workflow import SyncLicitacoesWorkflow
from src.pipeline.models.state import SyncParams
from src.pipeline.workers.sync_worker import TASK_QUEUE
from src.core.config import SETTINGS

async def run():
    client = await Client.connect(SETTINGS.temporal_host)
    result = await client.execute_workflow(
        SyncLicitacoesWorkflow.run,
        SyncParams(modalidades=[6, 8], lookback_horas=24),  # last 24 hours
        id="manual-sync-run",
        task_queue=TASK_QUEUE,
    )
    print(result)

asyncio.run(run())
EOF

python /tmp/manual_sync.py
```

The worker must be running (Step 5) for this to execute. Adjust `lookback_horas` to control how far back the sync reaches.

---

## Teardown

To stop all infrastructure services and remove their data volumes:

```bash
# Stop services, keep volumes (data is preserved)
docker compose down

# Stop services AND remove all data volumes (full reset)
docker compose down -v
```

After `down -v`, you will need to re-apply the Alembic migrations (Step 4) and re-create the Temporal schedule (Step 6) before running the pipeline again.