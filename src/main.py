from fastapi import FastAPI
from dotenv import load_dotenv
from src.api.router import router

load_dotenv()
from src.core.config import SETTINGS  # noqa: E402  Validates env vars at startup
_ = SETTINGS

app = FastAPI(title="Multi-Tenant Agent API")

# Register all routes through the central router
app.include_router(router)