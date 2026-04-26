from fastapi import FastAPI
from src.api.router import router
from src.core.config import SETTINGS  # Validates all env vars at startup
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Multi-Tenant Agent API")

# Register all routes through the central router
app.include_router(router)