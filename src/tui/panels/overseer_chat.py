from __future__ import annotations
from collections import deque
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static, Input, Markdown, LoadingIndicator
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.binding import Binding
from rich.text import Text
from rich.console import RenderableType


class OverseerChatPanel(Widget):
    """
    btop-style overseer console.
    Conversation history above, single-line input at the bottom.
    Input is a real Textual Input widget — always focusable.
    No padding wasted on labels/headers inside the widget.
    """

    DEFAULT_CSS = """
    OverseerChatPanel {
        border: round $primary;
        border-title-color: $primary;
        border-title-style: bold;
        background: $surface;
        padding: 0;
        height: 100%;
    }
    OverseerChatPanel:focus-within {
        border: round $accent;
    }
    #chat-scroll {
        height: 1fr;
        padding: 0 1;
        overflow-y: auto;
    }
    .msg-user {
        color: #7ec8e3;
        margin: 0 1;
    }
    .msg-agent {
        margin: 0 1;
    }
    .msg-loading {
        color: #fea62b;
    }
    #chat-divider {
        height: 1;
        color: $primary;
        padding: 0 1;
    }
    #chat-input {
        height: 1;
        border: none;
        background: $panel;
        padding: 0 1;
        color: white;
        margin: 0;
    }
    #chat-input:focus {
        border: none;
        background: $panel;
    }
    #input-row {
        height: 3;
        background: $panel;
        border-top: solid $primary;
        padding: 0;
    }
    #prompt-label {
        width: 4;
        color: #00d4aa;
        text-style: bold;
        padding: 1 0 0 1;
    }
    """

    BINDINGS = [
        Binding("enter", "submit", "Send", show=False),
        Binding("ctrl+l", "clear", "Clear", show=False),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._messages: deque[tuple[str, str]] = deque(maxlen=200)
        self.border_title = "OVERSEER CONSOLE"

    @property
    def messages(self) -> list[dict[str, str]]:
        """Expose messages for testing compatibility"""
        return [{"sender": sender, "content": content} for sender, content in self._messages]

    def compose(self) -> ComposeResult:
        from textual.containers import Horizontal
        yield ScrollableContainer(id="chat-scroll")
        with Horizontal(id="input-row"):
            yield Static("▶ ", id="prompt-label")
            yield Input(
                placeholder="message overseer...",
                id="chat-input",
            )

    def on_mount(self) -> None:
        self.query_one("#chat-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "chat-input":
            text = event.value.strip()
            if text:
                self.add_message("user", text)
                event.input.value = ""
                # Bubble up to app
                self.app.handle_overseer_input(text)  # type: ignore[attr-defined]

    def add_user_message(self, text: str) -> None:
        scroll = self.query_one("#chat-scroll")
        scroll.mount(Static(f"**you** {text}", classes="msg-user"))
        scroll.scroll_end(animate=False)

    def add_agent_message(self, agent_name: str, text: str) -> None:
        scroll = self.query_one("#chat-scroll")
        # Remove loading indicator for this agent if present
        for w in scroll.query(f".loading-{agent_name}"):
            w.remove()
        # Render full markdown response
        md = Markdown(f"**{agent_name}** \n\n{text}", classes="msg-agent")
        scroll.mount(md)
        scroll.scroll_end(animate=False)

    def show_agent_loading(self, agent_name: str) -> None:
        scroll = self.query_one("#chat-scroll")
        indicator = LoadingIndicator(classes=f"msg-loading loading-{agent_name}")
        scroll.mount(indicator)
        scroll.scroll_end(animate=False)

    def add_message(self, sender: str, content: str) -> None:
        """Backward compatibility method"""
        if sender == "user":
            self.add_user_message(content)
        else:
            self.add_agent_message(sender, content)

    def action_submit(self) -> None:
        inp = self.query_one("#chat-input", Input)
        text = inp.value.strip()
        if text:
            self.add_message("user", text)
            inp.value = ""
            self.app.handle_overseer_input(text)  # type: ignore[attr-defined]

    def action_clear(self) -> None:
        self._messages.clear()
        self._refresh_history()