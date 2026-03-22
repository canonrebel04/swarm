from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from src.tui.panels.agent_fleet   import AgentFleetPanel
from src.tui.panels.agent_output  import AgentOutputPanel
from src.tui.panels.event_log     import EventLogPanel
from src.tui.panels.overseer_chat import OverseerChatPanel
from src.tui.panels.task_graph    import TaskGraphPanel


class MainScreen(Screen):

    CSS = """
    MainScreen {
        layout: vertical;
        background: $background;
    }

    /* ── Statusbar (top, 1 row) ─────────────────────── */
    #statusbar {
        height: 1;
        background: $panel;
        color: $text-muted;
        padding: 0 1;
        layout: horizontal;
    }
    #status-left  { width: 1fr; }
    #status-mid   { width: 1fr; text-align: center; color: $primary; text-style: bold; }
    #status-right { width: 1fr; text-align: right; }

    /* ── Main body ──────────────────────────────────── */
    #body {
        height: 1fr;
        layout: horizontal;
    }

    /* Left column: overseer 40% + graph 30% + events 30% */
    #left-col {
        width: 2fr;
        layout: vertical;
    }
    OverseerChatPanel { height: 40%; }
    TaskGraphPanel    { height: 30%; border: solid $primary 10%; }
    EventLogPanel     { height: 30%; }

    /* Right column: fleet top 55% + output 45% */
    #right-col {
        width: 3fr;
        layout: vertical;
    }
    AgentFleetPanel   { height: 11fr; }
    AgentOutputPanel  { height: 9fr; }

    /* ── Footerbar (bottom, 1 row) ──────────────────── */
    #footerbar {
        height: 1;
        background: $panel;
        color: $text-muted;
        layout: horizontal;
        padding: 0 1;
    }
    #footer-bindings { width: 1fr; }
    #footer-stats    { width: 1fr; text-align: right; color: $text-muted; }
    """

    def compose(self) -> ComposeResult:
        # ── Top statusbar (1 row, like btop's cpu header) ─────────────────
        with Horizontal(id="statusbar"):
            yield Static("", id="status-left")
            yield Static("⬡  swarm  —  multi-agent runtime", id="status-mid")
            yield Static("00:00:00", id="status-right")

        # ── Main body ─────────────────────────────────────────────────────
        with Horizontal(id="body"):
            with Vertical(id="left-col"):
                yield OverseerChatPanel()
                # Task graph will be updated by the app once coordinator is ready
                yield TaskGraphPanel(id="task-graph")
                yield EventLogPanel()
            with Vertical(id="right-col"):
                yield AgentFleetPanel()
                yield AgentOutputPanel()

        # ── Bottom footerbar (bindings, like btop's bottom bar) ───────────
        with Horizontal(id="footerbar"):
            yield Static(
                "^q Quit  ^k Kill  ^r Retry  ^n New  F2 Model  ^i Role  ^s Skills  ^p Palette",
                id="footer-bindings",
            )
            yield Static("0 agents  ·  0 events", id="footer-stats")

    def update_statusbar(self, agents: int, runtime: str, elapsed: str) -> None:
        try:
            self.query_one("#status-left",  Static).update(f"○ {runtime}")
        except Exception:
            pass  # widget not ready yet
        try:
            self.query_one("#status-right", Static).update(elapsed)
        except Exception:
            pass  # widget not ready yet
        try:
            self.query_one("#footer-stats", Static).update(f"{agents} agents  ·  0 events")
        except Exception:
            pass  # widget not ready yet
