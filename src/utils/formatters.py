"""Formatters for the agent."""
from typing import List, Any

def build_capabilities(tools: List[Any]) -> str:
    """Build the tools/capabilities for the agent."""
    return "\n".join(
        f"- {t.name}: {t.description}"
        for t in tools
    )