from __future__ import annotations
from collections import deque
from datetime import datetime
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from rich.text import Text
from rich.console import RenderableType

LEVEL_STYLE = {
    "info":  ("·", "#3a7080"),
    "spawn": ("▶", "bright_green"),
    "done":  ("✓", "cyan"),
    "warn":  ("⚠", "dark_orange"),
    "error": ("✗", "red1"),
    "kill":  ("✗", "red1"),
    "merge": ("⇌", "medium_purple1"),
    "handoff":("→","yellow1"),
}


class EventLogPanel(Widget):
    """
    btop-style event log — tight rows, timestamp + icon + source + message.
    No border title widget — embedded in border.
    """

    DEFAULT_CSS = """
    EventLogPanel {
        border: round $accent;
        border-title-color: $accent;
        border-title-style: bold;
        background: $surface;
        padding: 0 1;
        height: 100%;
    }
    #event-content {
        height: 100%;
        overflow-y: auto;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._events: deque[tuple[str, str, str, str]] = deque(maxlen=200)
        self.border_title = "EVENTS"

    def compose(self) -> ComposeResult:
        yield Static("[#3a5060]no events yet[/#3a5060]", id="event-content", markup=True)

    def push_event(self, level: str, source: str, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._events.append((ts, level, source, message))
        self._refresh()

    def _refresh(self) -> None:
        try:
            self.query_one("#event-content", Static).update(self._render_content())
        except Exception:
            pass

    def _render_content(self) -> str:
        """Return a string with Rich markup that Static widget can handle"""
        if not self._events:
            return "[#3a5060]no events yet[/#3a5060]"
        
        lines = []
        for ts, level, source, msg in self._events:
            icon, color = LEVEL_STYLE.get(level, ("·", "#3a5060"))
            line = f"{ts} {icon} {source:<14.14} {msg}"
            lines.append(f"[{color}]{line}[/{color}]")
        return "\n".join(lines)
    
    def _render(self):
        """Override _render to delegate to the Static widget"""
        return self.query_one("#event-content", Static).render()