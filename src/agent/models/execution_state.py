from typing_extensions import Annotated
from langgraph.graph import MessagesState
from src.agent.models.outputs import Task, ResearchPlan, Context, ExecutionPlan, RunResults


def replace(_: str, new: str) -> str:
    return new

class ExecutionState(MessagesState):
    """Execution state for the agent."""

    phase: Annotated[str, replace]
    query: Annotated[str, replace]
    task: Annotated[Task, replace]
    research_plan: Annotated[ResearchPlan, replace]
    context: Annotated[Context, replace]
    execution_plan: Annotated[ExecutionPlan, replace]
    step_counter: Annotated[int, replace]
    results: Annotated[RunResults, replace]
    llm_calls: Annotated[int, replace]