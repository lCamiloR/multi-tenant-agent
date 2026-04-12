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
