import pprint
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

            response = None
            
            with Live(refresh_per_second=6, console=console) as live:
                for event in self.agent.invoke(user_input):
                    node_name, state_update = next(iter(event.items()))
                    live.console.print(f"\f[bold magenta]=== Event: {node_name} ===[/bold magenta]")
                    live.console.print(pprint.pformat(event))

                    if "steps" in state_update:
                        renderer.set_steps(state_update["steps"])

                    if "current_step" in state_update:
                        renderer.set_current_step(state_update["current_step"])

                    if state_update.get("messages"):
                        response = state_update["messages"].pop()
                    else:
                        response = None

                    live.update(renderer.render())

            if response:
                log_panel(
                    response.content,
                    title="AI",
                    style="ai",
                    console=console
                )

                