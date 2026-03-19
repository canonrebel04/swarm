"""
Event Log Panel
"""

from datetime import datetime
from textual.app import ComposeResult
from textual.widgets import RichLog, Label
from textual.containers import Vertical


LEVEL_STYLE = {
    "info":  "[dim #5a6a80]",
    "warn":  "[#f9e718]",
    "error": "[bold #ff2d6b]",
    "spawn": "[#39ff14]",
    "kill":  "[#ff1c1c]",
    "done":  "[dim #3a4255]",
    "drift": "[bold #ff6b1a]",
}

LEVEL_ICON = {
    "info":  "·",
    "warn":  "⚠",
    "error": "✗",
    "spawn": "▶",
    "kill":  "■",
    "done":  "✓",
    "drift": "⚡",
}


class EventLogPanel(Vertical):

    def compose(self) -> ComposeResult:
        yield Label("⚡  EVENTS", classes="panel--title panel--title-orange")
        yield RichLog(
            id="event-log-widget",
            highlight=False,
            markup=True,
            wrap=True,
            max_lines=500,
        )

    def push_event(self, level: str, source: str, message: str) -> None:
        log  = self.query_one("#event-log-widget", RichLog)
        ts   = datetime.now().strftime("%H:%M:%S")
        s    = LEVEL_STYLE.get(level, "[dim]")
        icon = LEVEL_ICON.get(level, "·")
        log.write(f"[dim]{ts}[/] {s}{icon} [{source}] {message}[/]")