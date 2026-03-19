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
    messages: list = []

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
        self.add_message("user", text)
        
        # Push user input event
        if hasattr(self, 'app') and hasattr(self.app, 'push_swarm_event'):
            message_preview = text[:60] + "…" if len(text) > 60 else text
            self.app.push_swarm_event("info", "user", message_preview)
        
        # Stream the response
        self.stream_response(text)

    def add_message(self, sender: str, text: str) -> None:
        """Add a message to the chat"""
        self.messages.append({"sender": sender, "content": text})
        self._write_message(sender, text)

    def _write_message(self, sender: str, text: str) -> None:
        try:
            log = self.query_one("#chat-log", RichLog)
            ts    = datetime.now().strftime("%H:%M:%S")
            style = SENDER_STYLE.get(sender, "[dim]")
            icon  = ICONS.get(sender, "·")
            log.write(f"[dim]{ts}[/] {style}{icon}[/] {text}")
        except Exception:
            # Widget not mounted yet, skip
            pass

    @work(exclusive=True, thread=False)
    async def stream_response(self, text: str) -> None:
        """Stream the coordinator's response to user input."""
        self.thinking = True
        try:
            # Get coordinator from app
            if hasattr(self, 'app') and hasattr(self.app, 'coordinator'):
                coordinator = self.app.coordinator
                
                # Stream the response token by token
                async for token in coordinator.handle_user_input(text):
                    self.push_token(token)
                
                # Add newline after streaming
                self.push_token("\n")
            else:
                self.add_message("overseer", "[dim]no coordinator connected yet[/]")
        finally:
            self.thinking = False

    def push_token(self, token: str) -> None:
        log = self.query_one("#chat-log", RichLog)
        log.write(token, shrink=False, scroll_end=True)

    def push_system(self, msg: str) -> None:
        self.add_message("system", msg)