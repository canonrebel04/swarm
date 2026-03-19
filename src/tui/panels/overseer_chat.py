"""
Overseer Chat Panel
"""

import asyncio
from datetime import datetime
from textual.app import ComposeResult
from textual.widgets import RichLog, Input, Label
from textual.containers import Vertical
from textual.reactive import reactive
from textual import work


SENDER_STYLE = {
    "user":     "[bold #f9e718]",
    "overseer": "[bold #00e5ff]",
    "system":   "[dim #3a4255]",
}

ICONS = {
    "user":     "▸",
    "overseer": "◈",
    "system":   "·",
}


class OverseerChatPanel(Vertical):
    thinking: reactive[bool] = reactive(False)

    def compose(self) -> ComposeResult:
        yield Label("◈  OVERSEER CONSOLE", classes="panel--title panel--title-cyan")
        yield RichLog(
            id="chat-log",
            highlight=False,
            markup=True,
            wrap=True,
            max_lines=1000,
        )
        yield Input(
            placeholder="  ▸ message overseer…",
            id="nudge-input",
        )

    def watch_thinking(self, value: bool) -> None:
        log = self.query_one("#chat-log", RichLog)
        if value:
            log.write("[dim #004d5e]  ◌ overseer processing…[/]")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.clear()
        self._write_message("user", text)
        self.thinking = True
        self._send(text)

    def _write_message(self, sender: str, text: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        ts    = datetime.now().strftime("%H:%M:%S")
        style = SENDER_STYLE.get(sender, "[dim]")
        icon  = ICONS.get(sender, "·")
        log.write(f"[dim]{ts}[/] {style}{icon}[/] {text}")

    @work(exclusive=False, thread=False)
    async def _send(self, text: str) -> None:
        await asyncio.sleep(0)
        # Replace with real overseer call + token streaming
        self._write_message("overseer", "[dim]no overseer connected yet[/]")
        self.thinking = False

    def push_token(self, token: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(token, shrink=False, scroll_end=True)

    def push_system(self, msg: str) -> None:
        self._write_message("system", msg)