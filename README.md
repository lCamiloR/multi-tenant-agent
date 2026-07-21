# multi-tenant-agent

## Project goal

**multi-tenant-agent** is a multi-tenant, agentic assistant that helps companies discover and evaluate Brazilian government procurement opportunities (*licitações*) that match their business domain.

Instead of manually scanning the PNCP (Portal Nacional de Contratações Públicas) portal, a company's user logs in, describes what their business does (or asks a direct question), and the agent:

1. Interprets the request and decides which tools it needs (planning / task decomposition).
2. Searches procurement data semantically — matching business domain descriptions against active and historical *licitações* — and/or retrieves specific records by control number.
3. Reads, writes, and organizes supporting local files (notes, extracted summaries, generated reports) inside a sandboxed workspace, scoped to the requesting tenant.
4. Consolidates the results into an actionable, business-oriented answer, with suggested next steps.

Every interaction is scoped to a **tenant**: users must authenticate first, and all data access, memory, and file operations are isolated per tenant so that one company's data, conversation history, and files are never visible to another.

Implementation choices favor **explicit, from-scratch construction** of core agentic components (e.g. LangGraph nodes/tools, JWT auth, ingestion pipelines) over higher-level abstractions, even where a framework shortcut exists.

## Systems involved

| System | Role |
|---|---|
| **PNCP API** | External source of Brazilian public procurement data (*licitações*, *órgãos*, modalidades). |
| **Temporal** | Orchestrates the recurring ingestion pipeline (`SyncLicitacoesWorkflow`) that pages through the PNCP API, using `continue_as_new` to stay within workflow history limits. |
| **PostgreSQL** | Structured store for procurement and procuring-entity records, accessed via async SQLAlchemy + a repository layer, versioned with Alembic. |
| **Milvus** (+ etcd, MinIO, Attu) | Vector store for semantic search over procurement descriptions, populated with OpenAI (`text-embedding-3-small`) embeddings. |
| **MCP Server** (`src/mcp_server`) | Exposes procurement search/retrieval as MCP tools (`search_procurements`, `get_procurement_details`, `get_multiple_procurement_details`) over SSE, consumable by the LangGraph agent via `langchain-mcp-adapters`, or by any other MCP-compatible client. |
| **LangGraph agent** (`src/agent`) | The reasoning core: a graph-based agent (planning → context gathering → execution → wrap-up) that combines MCP procurement tools with local filesystem tools to fulfill user requests. |
| **FastAPI** (`src/api`, `src/main.py`) | HTTP surface for authentication and agent interaction endpoints. |
| **JWT Auth** (`src/auth`) | Multi-tenant authentication: every token embeds a `tenant_id`, enforced via FastAPI dependencies before any agent or data access. |
| **Langfuse** | Observability/tracing for agent runs (LLM calls, tool usage, latency). |

## Target directory structure

```
multi-tenant-agent/
├── pyproject.toml
├── uv.lock
├── docker-compose.yml
├── .env
├── .env.example
└── src/
    ├── main.py                        # App entrypoint (FastAPI app / shell runner)
    │
    ├── agent/                         # LangGraph reasoning core
    │   ├── base.py                    # AgentBase — abstract interface (invoke)
    │   ├── graph_agent.py             # StateGraph construction: nodes, edges, planning/execution phases
    │   ├── models/
    │   │   ├── enums.py                # Phases (INITIAL, PLANNING, EXECUTING, ...)
    │   │   ├── execution_state.py      # Graph state schema
    │   │   └── outputs.py              # Structured outputs: Task, ExecutionPlan, RunResults, ...
    │   └── tools/
    │       └── file_system.py          # Sandboxed local file tools (read/write/search), tenant-scoped WORKDIR
    │
    ├── agent_shell/
    │   └── shell_chat.py               # CLI-based chat runner for local development/testing of the agent
    │
    ├── auth/                          # Multi-tenant authentication
    │   ├── jwt_handler.py              # create_access_token, verify_token
    │   ├── dependencies.py             # FastAPI Depends() for auth-protected routes
    │   └── models.py                   # LoginRequest, TokenResponse, TokenPayload (with tenant_id)
    │
    ├── api/                           # HTTP layer
    │   ├── router.py                   # Aggregates all sub-routers
    │   └── routes/
    │       ├── agent.py                 # Agent interaction endpoint(s)
    │       └── auth.py                  # POST /auth/token (login)
    │
    ├── core/
    │   └── config.py                   # Settings via pydantic-settings, validated at startup
    │
    ├── db/                             # Structured data layer (PostgreSQL)
    │   ├── base.py                      # Declarative base / engine setup
    │   ├── session.py                   # get_session (FastAPI) and get_session_ctx (Temporal activities)
    │   ├── models/
    │   │   ├── procurement.py
    │   │   └── procuring_entity.py
    │   └── repositories/
    │       ├── procurement_repo.py
    │       └── procuring_entity_repo.py
    │
    ├── mcp_server/
    │   └── procurement_server.py       # FastMCP server exposing procurement search/retrieval tools (SSE)
    │
    ├── pipeline/                       # Temporal-based ingestion pipeline
    │   ├── workflows/
    │   │   └── sync_workflow.py         # SyncLicitacoesWorkflow (continue_as_new pagination)
    │   ├── activities/
    │   │   ├── fetch_activity.py        # Pulls pages from the PNCP API
    │   │   └── upsert_activity.py       # Persists to PostgreSQL + upserts embeddings into Milvus
    │   ├── clients/
    │   │   ├── pncp_client.py           # PNCP API HTTP client
    │   │   ├── embedding_client.py      # OpenAI embeddings client
    │   │   └── milvus_client.py         # Milvus collection client
    │   ├── mappers/
    │   │   └── pncp_mapper.py           # Pure DTO → ORM translation
    │   ├── models/
    │   │   ├── pncp.py                  # PNCP API DTOs
    │   │   └── state.py                 # SyncProgress (continue_as_new payload)
    │   └── workers/
    │       ├── sync_worker.py           # Temporal worker process
    │       └── create_schedule.py       # Provisions the recurring sync schedule
    │
    └── utils/
        ├── formatters.py
        ├── loggers.py
        └── renderers.py
```

## Local development server

From the project root, with dependencies installed and your virtual environment activated:

**FastAPI CLI** — uses `[tool.fastapi]` / `entrypoint = "src.main:app"` in `pyproject.toml`:

```bash
fastapi dev
```

**FastAPI CLI (explicit path):**

```bash
fastapi dev src/main.py
```

**Uvicorn:**

```bash
uvicorn src.main:app --reload
```

If `fastapi` or `uvicorn` is not found, install the project (e.g. `pip install -e .`) so the CLI tools are available on your `PATH`.

## Supporting infrastructure

Run `docker compose up -d` to start local containers (PostgreSQL, Milvus + etcd + MinIO + Attu, Temporal + Temporal UI). See `src/pipeline/README.md` for the full ingestion pipeline setup (migrations, worker, sync schedule).