from rich.console import Console
from rich.live import Live

from utils.loggers import log_panel, log_text
from src.agent.base import AgentBase
from utils.renderers import PlanningRenderer


renderer = PlanningRenderer()


class ShellChat:
    """Class responsable for executing the Agent Custom Shell log interactions."""

    def __init__(self, agent: AgentBase):
        """Start the ShellChat class."""
        self.agent = agent
        self.console = Console()

    def run(self):
        """Execute log tracing."""
        console = self.console

        log_text("Your personal assistant is ready to help you.", level="info", console=console)
        log_text("Type 'exit' to end the chat.\n", level="info", console=console)

        while True:
            user_input = console.input("[bold yellow]You:[/bold yellow] ")

            if user_input.lower() in ["sair", "exit", "quit"]:
                log_text("Ending chat...", level="danger", console=console)
                break

            log_panel(user_input, title="You", style="user", console=console)

            final_results = None

            with Live(refresh_per_second=6, console=console) as live:
                for event in self.agent.invoke(user_input):
                    _, state_update = next(iter(event.items()))

                    if "steps" in state_update:
                        renderer.set_steps(state_update["steps"])

                    if "current_step" in state_update:
                        renderer.set_current_step(state_update["current_step"])

                    if "results" in state_update:
                        final_results = state_update["results"]

                    live.update(renderer.render())

            if final_results:
                log_panel(
                    final_results.results_consolidation,
                    title="AI",
                    style="ai",
                    console=console
                )

                if final_results.next_steps:
                    log_panel(
                        final_results.next_steps,
                        title="Next steps",
                        style="info",
                        console=console
                    )