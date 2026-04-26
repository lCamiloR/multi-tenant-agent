from fastapi import APIRouter, Depends
from src.auth.dependencies import get_current_user, get_tenant_id
from src.auth.models import TokenPayload
from src.agent.graph_agent import GraphAgent
from src.core.config import SETTINGS
from pydantic import BaseModel
import os

router = APIRouter(tags=["agent"])
agent = GraphAgent("claude-haiku-4-5", api_key=SETTINGS.anthropic_api_key)

class UserInput(BaseModel):
    prompt: str

@router.post("/invoke")
def invoke(
    input: UserInput,
    # FastAPI resolves these automatically before calling this function.
    # If the token is missing or invalid, the request never reaches here.
    user: TokenPayload = Depends(get_current_user),
    tenant_id: str = Depends(get_tenant_id),
):
    """
    By the time this function runs, we already know:
    - Who the user is (user.sub)
    - Which tenant they belong to (tenant_id)
    - What role they have (user.role)
    """
    return agent.invoke(input.prompt, tenant_id=tenant_id)