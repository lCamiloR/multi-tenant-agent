from fastapi import FastAPI
from dotenv import load_dotenv
from src.api.router import router

from src.agent_shell.shell_chat import ShellChat
from src.agent.graph_agent import GraphAgent

load_dotenv()
from src.core.config import SETTINGS  # noqa: E402  Validates env vars at startup
_ = SETTINGS

# app = FastAPI(title="Multi-Tenant Agent API")

# # Register all routes through the central router
# app.include_router(router)

def main():
    agent = GraphAgent(model="claude-haiku-4-5", api_key=SETTINGS.anthropic_api_key)
    shell_agent = ShellChat(agent)

    shell_agent.run()

if __name__ == "__main__":
    main()