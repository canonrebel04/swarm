from __future__ import annotations
from collections import deque
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static
from textual.reactive import reactive
from rich.text import Text
from rich.console import RenderableType
import re

ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\\[[0-?]*[ -/]*[@-~])")

# Tool line prefixes → short colored label + icon
TOOL_LABELS = {
    "[bash]":    ("⬡ bash",    "dark_orange"),
    "[read]":    ("◈ read",    "steel_blue"),
    "[write]":   ("✎ write",   "medium_purple1"),
    "[edit]":    ("✏ edit",    "medium_purple1"),
    "[glob]":    ("⌕ glob",    "grey62"),
    "[grep]":    ("⌕ grep",    "grey62"),
    "[fetch]":   ("⬇ fetch",   "cyan"),
    "[result]":  ("◉ result",  "grey42"),
    "[error]":   ("✗ error",   "red1"),
    "[done]":    ("✓ done",    "bright_green"),
    "[handoff→]":("→ handoff", "yellow1"),
    "[files]":   ("∷ files",   "cyan"),
    "[step]":    ("· step",    "grey42"),
    "[task]":    ("⊕ task",    "bright_blue"),
    "[tools]":   ("⊞ tools",   "grey62"),
    "[model]":   ("◈ model",   "grey42"),
}


class AgentOutputPanel(Widget):
    """
    btop-style output panel.
    - No Rich Markup in stored lines — only applied at render time
    - Tool lines get colored prefix labels (like btop's metric names)
    - Text is right-clipped, never wraps messily
    - Auto-scrolls, keeps last 500 lines
    """

    DEFAULT_CSS = """
    AgentOutputPanel {
        border: round $secondary;
        border-title-color: $secondary;
        border-title-style: bold;
        background: $surface;
        padding: 0 1;
        height: 100%;
    }
    AgentOutputPanel:focus-within {
        border: round $accent;
    }
    #output-content {
        height: 100%;
        overflow-y: auto;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._lines: deque[str] = deque(maxlen=500)
        self._current_agent: str | None = None
        self.border_title = "OUTPUT"

    @property
    def current_agent(self) -> str | None:
        """Expose current agent for testing compatibility"""
        return self._current_agent

    def compose(self) -> ComposeResult:
        yield Static(self._render_output(), id="output-content", markup=True)

    def set_agent(self, name: str) -> None:
        self._current_agent = name
        self.border_title = f"OUTPUT  [{name}]"
        self._lines.clear()
        self._refresh()

    def push_line(self, line: str) -> None:
        clean = ANSI_ESCAPE.sub("", line).rstrip()
        if clean:
            self._lines.append(clean)
            self._refresh()

    def _refresh(self) -> None:
        try:
            widget = self.query_one("#output-content", Static)
            widget.update(self._render_output())
        except Exception:
            pass

    def _render_output(self) -> RenderableType:
        text = Text()
        if not self._lines:
            text.append("select an agent to view output", style="#3a5060")
            return text
        
        for raw in self._lines:
            self._format_line(text, raw)
        return text

    def _format_line(self, text: Text, line: str) -> None:
        for prefix, (label, color) in TOOL_LABELS.items():
            if line.startswith(prefix):
                rest = line[len(prefix):].strip()
                text.append(f"{label} {rest}", style=color)
                text.append("\n")
                return

        # Plain assistant text
        text.append(f"{line}\n", style="#8ab4cc")