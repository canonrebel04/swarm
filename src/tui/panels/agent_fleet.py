"""
Agent Fleet Panel
"""

from textual.app import ComposeResult
from textual.widgets import DataTable, Label
from textual.containers import Vertical
from ..state import AgentRow


# Cyberpunk role markup
ROLE_M = {
    "orchestrator": "[bold #bd00ff]⬡ orchestrator[/]",
    "coordinator":  "[#818cf8]⬡ coordinator[/]",
    "supervisor":   "[#00e5ff]⬡ supervisor[/]",
    "lead":         "[#38bdf8]⬡ lead[/]",
    "scout":        "[#39ff14]◉ scout[/]",
    "developer":    "[#00e5ff]⟨⟩ developer[/]",
    "builder":      "[#f9e718]⚙ builder[/]",
    "tester":       "[#ff6b1a]✦ tester[/]",
    "reviewer":     "[#ff2d6b]◈ reviewer[/]",
    "merger":       "[#bd00ff]⇢ merger[/]",
    "monitor":      "[dim]◌ monitor[/]",
}

STATE_M = {
    "running": "[bold #39ff14]● running[/]",
    "queued":  "[#f9e718]◌ queued[/]",
    "stalled": "[bold #ff2d6b]⚠ stalled[/]",
    "done":    "[dim #3a4255]✓ done[/]",
    "error":   "[bold #ff1c1c]✗ error[/]",
    "blocked": "[#ff6b1a]⏸ blocked[/]",
    "idle":    "[dim #3a4255]— idle[/]",
}

COLS = ("Name", "Role", "State", "Task", "Runtime", "PID")


class AgentFleetPanel(Vertical):

    def compose(self) -> ComposeResult:
        yield Label("⚙  AGENT FLEET", classes="panel--title panel--title-yellow")
        t = DataTable(id="fleet-table", cursor_type="row", zebra_stripes=True)
        t.add_columns(*COLS)
        yield t

    def upsert_agent(self, agent: AgentRow) -> None:
        t = self.query_one("#fleet-table", DataTable)
        role_m  = ROLE_M.get(agent.role, agent.role)
        state_m = STATE_M.get(agent.state, agent.state)
        task_s  = agent.task[:38] + "…" if len(agent.task) > 38 else agent.task
        pid_s   = str(agent.pid) if agent.pid else "—"
        row     = (agent.name, role_m, state_m, task_s, agent.runtime, pid_s)
        try:
            # exists → update in place, no flicker, no width recalc
            idx = t.get_row_index(agent.name)
            for ci, val in enumerate(row):
                t.update_cell_at((idx, ci), val, update_width=False)
        except Exception:
            t.add_row(*row, key=agent.name)

    def remove_agent(self, name: str) -> None:
        t = self.query_one("#fleet-table", DataTable)
        try:
            t.remove_row(name)
        except Exception:
            pass

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        # Notify app of selection
        self.app.selected_agent = str(event.row_key.value)