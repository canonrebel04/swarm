"""
Task Graph Panel for TUI
Visualizes task dependencies and execution status.
"""

from textual.app import ComposeResult
from textual.widgets import Static, Label
from textual.containers import Vertical, ScrollableContainer
from rich.table import Table
from rich.tree import Tree
from rich.text import Text


class TaskGraphPanel(Static):
    """Panel for visualizing the Directed Acyclic Graph (DAG) of tasks."""

    def __init__(self, coordinator=None, **kwargs):
        super().__init__(**kwargs)
        self.coordinator = coordinator

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("◈  TASK GRAPH / DEPENDENCIES  ◈", id="graph-title")
            with ScrollableContainer(id="graph-scroll"):
                yield Static(id="graph-content")

    def update_graph(self):
        """Re-render the task graph representation."""
        if not self.coordinator:
            return

        # Fetch current state from coordinator
        queue = self.coordinator._task_queue
        history = self.coordinator._task_history
        all_tasks = queue + history

        if not all_tasks:
            self.query_one("#graph-content", Static).update("No tasks active.")
            return

        # Simple table view for now, could be upgraded to Tree
        table = Table(box=None, expand=True, show_header=True)
        table.add_column("Task Title", style="cyan", no_wrap=True)
        table.add_column("Depends On", style="dim")
        table.add_column("Status", justify="center")

        status_colors = {
            "pending": "dim",
            "blocked": "red",
            "ready": "yellow",
            "active": "green",
            "completed": "bright_green",
            "failed": "bright_red"
        }

        for task in all_tasks:
            deps = ", ".join(task.depends_on) if task.depends_on else "-"
            status_style = status_colors.get(task.status, "white")
            table.add_row(
                task.title,
                deps,
                Text(task.status.upper(), style=f"bold {status_style}")
            )

        self.query_one("#graph-content", Static).update(table)

    def on_mount(self) -> None:
        self.update_graph()
        # Refresh graph every 2 seconds
        self.set_interval(2.0, self.update_graph)
