# multi-tenant-agent

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

# target structure
```
multi-tenant-agent/
├── pyproject.toml
├── uv.lock
├── .env
├── .env.example
└── src/
    ├── main.py
    ├── agent/
    │   ├── graph_agent.py
    │   └── models.py
    ├── auth/
    │   ├── __init__.py
    │   ├── jwt_handler.py      # create_access_token, verify_token
    │   ├── dependencies.py     # Depends() injetáveis no FastAPI
    │   └── models.py           # TokenPayload, TokenResponse (Pydantic)
    ├── api/
    │   ├── __init__.py
    │   ├── router.py           # Agrega todos os routers
    │   └── routes/
    │       ├── __init__.py
    │       ├── agent.py        # POST / (endpoint do agente)
    │       └── auth.py         # POST /auth/token
    └── core/
        ├── __init__.py
        └── config.py           # Settings via pydantic-settings
```