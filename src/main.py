from fastapi import FastAPI
from pydantic import BaseModel
from src.agent.graph_agent import GraphAgent
import os
from dotenv import load_dotenv

load_dotenv()
agent = GraphAgent("claude-haiku-4-5", api_key=os.getenv("ANTHROPIC_API_KEY"))

app = FastAPI()


class UserInput(BaseModel):
    prompt: str


@app.post("/")
def invoke(input: UserInput):
    return agent.invoke(input.prompt)
