from pydantic import BaseModel, Field
from typing import List



# thoughts: str = Field(
#         ...,
#         description="Thoughts and observations generated during execution"
#     )

"""
Task represents the refined task — a clear, objective description of what needs to be done,
along with the user's intent summarized in a single sentence. This structure is essential
for guiding research plan execution and context gathering, ensuring all actions remain
aligned with the user's ultimate goal.
"""
class Task(BaseModel):
    description: str = Field(
        ...,
        description="Clear and objective description of the refined task"
    )
    intent: str = Field(
        ...,
        description="User's intent summarized in a single sentence"
    )


class PlanItem(BaseModel):
    quick_description: str = Field(
        ...,
        description="Short, direct description of the action to be executed"
    )
    detailed_description: str = Field(
        ...,
        description="Detailed description of the action, including how to execute it and what outcome to expect"
    )
    tools_suggestions: List[str] = Field(
        default_factory=list,
        description="List of suggested tools to execute the action"
    )

"""
ResearchPlan is a structure that organizes the execution steps for context gathering.
Each PlanItem represents a specific action to be performed, with a quick description
for reference and a detailed description for guidance.
"""
class ResearchPlan(BaseModel):
    steps: List[PlanItem] = Field(
        default_factory=list,
        description="Ordered execution steps for context gathering"
    )

"""
ContextItem represents a piece of information collected during research plan execution.
It includes a short title to summarize the information, the relevant content collected,
and the source it was obtained from. Context is a collection of these items, organized
in a list, serving as the basis for executing the refined task.
"""
class ContextItem(BaseModel):
    title: str = Field(
        ...,
        description="Short title summarizing the collected information"
    )
    content: str = Field(
        ...,
        description="Relevant content collected"
    )
    source: str = Field(
        ...,
        description="Origin of the information (e.g. tool or source)"
    )


class Context(BaseModel):
    items: List[ContextItem] = Field(
        default_factory=list,
        description="List of collected context items"
    )

"""
ExecutionPlan is the structure that organizes the execution steps for carrying out the
refined task, based on the collected context. Each PlanItem represents a specific action
to be performed, with a quick description for reference and a detailed description for
guidance, plus tool suggestions. ExecutionPlan is essential to ensure the task execution
is aligned with the user's goal and that all actions are performed efficiently.
"""

class ExecutionPlan(BaseModel):
    steps: List[PlanItem] = Field(
        default_factory=list,
        description="Ordered steps for execution"
    )


class UsedTool(BaseModel):
    name: str = Field(
        ...,
        description="Name of the tool used"
    )
    description: str = Field(
        ...,
        description="Description of what the tool did"
    )

"""
Used for consolidating execution results — listing the tools used, problems or
limitations encountered during execution, a final consolidated message to be delivered
to the user, and a text suggesting next steps. This structure is essential for providing
clear and useful feedback, helping the user understand what was done, the results, and
what next actions are recommended.
"""

class RunResults(BaseModel):
    used_tools: List[UsedTool] = Field(
        default_factory=list,
        description="List of tools used during execution"
    )
    detected_problems: List[str] = Field(
        default_factory=list,
        description="Problems or limitations encountered during execution"
    )
    results_consolidation: str = Field(
        ...,
        description="Final consolidated message to be delivered to the user"
    )
    next_steps: str = Field(
        ...,
        description="Text suggesting next steps for the user"
    )


class IsStepComplete(BaseModel):
    """Indicates whether a step was executed correctly"""
    isComplete: bool = Field(description="Indicates whether the step was completed.")
    error: bool = Field(description="Indicates whether an error occurred during step execution.")
    motif: str = Field(description="Reason for the error, if any.")
