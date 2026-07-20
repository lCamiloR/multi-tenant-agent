from typing import List, Any, Optional
from rich.console import Group
from rich.text import Text


STEP_ICONS = {
    "done":    ("✔", "bold green"),
    "current": ("►", "bold cyan"),
    "pending": ("○", "dim"),
}


class PlanningRenderer:

    def __init__(self):
        self.steps: List[Any] = []
        self.current_step: Optional[int] = None

    def set_steps(self, steps: List[Any]):
        self.steps = steps

    def set_current_step(self, index: int):
        self.current_step = index

    def _get_step_text(self, step: Any) -> str:
        # supports both plain string and PlanItem
        if isinstance(step, str):
            return step

        # fallback to model attribute
        return getattr(step, "quick_description", str(step))

    def render(self):
        lines = []

        for i, step in enumerate(self.steps):
            line = Text()

            if self.current_step is not None:
                if i < self.current_step:
                    icon, style = STEP_ICONS["done"]
                elif i == self.current_step:
                    icon, style = STEP_ICONS["current"]
                else:
                    icon, style = STEP_ICONS["pending"]
            else:
                icon, style = STEP_ICONS["pending"]

            step_text = self._get_step_text(step)

            line.append(f"  {icon} ", style=style)
            line.append(f"{i + 1}. {step_text}", style=style if icon != "○" else "dim")
            lines.append(line)

        lines.append(Text(""))
        return Group(*lines)