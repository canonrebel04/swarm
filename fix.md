Here is a comprehensive breakdown of every fix needed, with the specific code changes for each issue. I'll address them in order of severity.

***

## 1. Fix `EventLogPanel` Rendering (Crash)

This is the remaining crash. All panels need to use `Static` instead of overriding `render()` directly:

**`src/tui/panels/event_log.py`** — replace the `render()` approach:
```python
from textual.app import ComposeResult
from textual.widgets import Static
from textual.widget import Widget

class EventLogPanel(Widget):
    DEFAULT_CSS = """
    EventLogPanel {
        border: round #fea62b;
        height: 2fr;
        padding: 0 1;
        background: #1e1e1e;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("no events yet", id="event-log-content")

    def add_event(self, text: str) -> None:
        content = self.query_one("#event-log-content", Static)
        content.update(text)
```

***

## 2. Model Keybinding (`m` → `ctrl+m`)

In your main app file (likely `src/tui/app.py`), find the `BINDINGS` list and update:

```python
# Before
BINDINGS = [
    ...
    Binding("m", "change_model", "Model"),
    Binding("ctrl+r", "retry", "Retry"),
    ...
]

# After
BINDINGS = [
    ...
    Binding("ctrl+m", "change_model", "Model"),
    Binding("ctrl+n", "new_chat", "New Chat"),   # replaces Retry
    ...
]
```

Also update the footer display if you use a `Footer` widget — it auto-reads from `BINDINGS`.

***

## 3. Agent Fleet — Clickable Rows with Auto-Select

Replace the fleet panel's static rendering with a `ListView`:

**`src/tui/panels/agent_fleet.py`**:
```python
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import ListView, ListItem, Label
from textual.reactive import reactive
from textual.message import Message

class AgentFleetPanel(Widget):
    selected_agent: reactive[str | None] = reactive(None)
    _follow_latest: bool = True

    class AgentSelected(Message):
        def __init__(self, agent_id: str) -> None:
            self.agent_id = agent_id
            super().__init__()

    DEFAULT_CSS = """
    AgentFleetPanel { border: round #fea62b; height: 1fr; }
    AgentFleetPanel ListView { height: 1fr; background: #1e1e1e; }
    AgentFleetPanel ListItem.--highlight { background: #003054; }
    """

    def compose(self) -> ComposeResult:
        yield ListView(id="agent-list")

    def add_agent(self, agent_id: str, name: str, role: str) -> None:
        lv = self.query_one("#agent-list", ListView)
        lv.append(ListItem(Label(f"● {name}  [{role}]"), id=f"agent-{agent_id}"))
        if self._follow_latest:
            # Auto-select the newest agent
            lv.index = len(lv.children) - 1
            self.selected_agent = agent_id
            self.post_message(self.AgentSelected(agent_id))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        self._follow_latest = False   # user manually selected, stop following
        agent_id = event.item.id.removeprefix("agent-")
        self.selected_agent = agent_id
        self.post_message(self.AgentSelected(agent_id))
```

In your app, handle the message to switch the output panel:
```python
def on_agent_fleet_panel_agent_selected(self, message: AgentFleetPanel.AgentSelected) -> None:
    self.query_one(AgentOutputPanel).show_agent(message.agent_id)
```

***

## 4. Clock Fix

The clock is frozen because the interval is likely not started or the reactive isn't refreshing. In your app:

```python
from textual.reactive import reactive
import time

class SwarmApp(App):
    _start_time: float = 0.0
    runtime: reactive[str] = reactive("00:00:00")

    def on_mount(self) -> None:
        self._start_time = time.monotonic()
        self.set_interval(1.0, self._tick_clock)

    def _tick_clock(self) -> None:
        elapsed = int(time.monotonic() - self._start_time)
        h, rem = divmod(elapsed, 3600)
        m, s = divmod(rem, 60)
        self.runtime = f"{h:02d}:{m:02d}:{s:02d}"

    def watch_runtime(self, value: str) -> None:
        self.query_one("#clock", Static).update(value)
```

Make sure your clock widget has `id="clock"` and is a `Static`.

***

## 5. Markdown Chat Rendering with Loading Animations

**`src/tui/panels/overseer_chat.py`** — use Textual's built-in `Markdown` widget and a `LoadingIndicator`:

```python
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Markdown, LoadingIndicator, ScrollableContainer
from textual.widgets import Static

class OverseerChatPanel(Widget):
    DEFAULT_CSS = """
    OverseerChatPanel { border: round #fea62b; height: 2fr; }
    OverseerChatPanel ScrollableContainer { height: 1fr; overflow-y: auto; }
    .msg-user { color: #7ec8e3; margin: 0 1; }
    .msg-agent { margin: 0 1; }
    .msg-loading { color: #fea62b; }
    """

    def compose(self) -> ComposeResult:
        yield ScrollableContainer(id="chat-scroll")

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
```

***

## 6. Rename Retry → New Chat

```python
# In BINDINGS:
Binding("ctrl+n", "new_chat", "New Chat"),

# Handler:
def action_new_chat(self) -> None:
    """Clear the current chat session."""
    chat = self.query_one(OverseerChatPanel)
    chat.query_one("#chat-scroll").remove_children()
    self.notify("Chat session cleared", severity="information")
```

***

## 7. Per-Agent Icons & Animations

For distinct per-agent visuals in the fleet and output panels, map agent roles to emoji icons:

```python
ROLE_ICONS = {
    "planner": "🧠",
    "coder":   "💻",
    "tester":  "🧪",
    "researcher": "🔍",
    "default": "🤖",
}

def agent_label(name: str, role: str, status: str) -> str:
    icon = ROLE_ICONS.get(role.lower(), ROLE_ICONS["default"])
    spinner = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"  # cycle through in watch_ reactive
    status_icon = "●" if status == "idle" else spinner[int(time.monotonic() * 10) % 10]
    return f"{status_icon} {icon} {name}  [{role}]"
```

Drive the spinner by refreshing the fleet panel on your 1-second clock tick:
```python
def _tick_clock(self) -> None:
    ...
    self.query_one(AgentFleetPanel).refresh()
```
