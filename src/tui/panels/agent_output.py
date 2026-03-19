"""
Agent Output Panel
"""

import re
from textual.app import ComposeResult
from textual.widgets import RichLog, Label
from textual.containers import Vertical


_ANSI = re.compile(r"\x1B(?:[@-Z\\-_]|\\[[0-?]*[ -/]*[@-~])")


class AgentOutputPanel(Vertical):
    _current: str | None = None

    def compose(self) -> ComposeResult:
        yield Label("◈  AGENT OUTPUT", classes="panel--title panel--title-purple")
        yield RichLog(
            id="output-log",
            highlight=True,
            markup=False,
            wrap=True,
            max_lines=2000,
        )

    def set_agent(self, name: str) -> None:
        if name == self._current:
            return
        self._current = name
        log = self.query_one("#output-log", RichLog)
        log.clear()
        log.write(f"── {name} ──")

    def push_line(self, raw: str) -> None:
        clean = _ANSI.sub("", raw)[:4096]
        self.query_one("#output-log", RichLog).write(clean)