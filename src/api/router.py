from fastapi import APIRouter
from src.api.routes import auth, agent

# The main router that aggregates everything
router = APIRouter()

router.include_router(auth.router)    # Mounts at /auth/token
router.include_router(agent.router)   # Mounts at /invoke