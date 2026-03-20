from __future__ import annotations
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import ListView, ListItem, Label
from textual.reactive import reactive
from textual.message import Message
import time

from src.tui.state import AgentRow

# Role → emoji icon
ROLE_ICONS = {
    "scout":       "🧠",
    "builder":     "💻",
    "developer":   "👨‍💻",
    "tester":      "🧪",
    "reviewer":    "🔍",
    "merger":      "🔗",
    "monitor":     "👁️",
    "coordinator": "🎯",
    "orchestrator":"🤖",
}

# Role → short color tag for Rich
ROLE_COLOR = {
    "scout":       "bright_blue",
    "builder":     "cyan",
    "developer":   "medium_purple1",
    "tester":      "dark_orange",
    "reviewer":    "orange_red1",
    "merger":      "hot_pink",
    "monitor":     "light_sky_blue1",
    "coordinator": "white",
    "orchestrator":"white",
}

STATE_COLOR = {
    "running":  "bright_green",
    "done":     "cyan",
    "error":    "red1",
    "stalled":  "dark_orange",
    "idle":     "grey42",
    "spawning": "yellow1",
}

STATE_ICON = {
    "running":  "▶",
    "done":     "✓",
    "error":    "✗",
    "stalled":  "⚠",
    "idle":     "○",
    "spawning": "◎",
}


class AgentFleetPanel(Widget):
    """
    btop-style agent fleet panel.
    Dense table, no wasted space, color-coded state + role.
    Title embedded in border, no separate header widget.
    """

    DEFAULT_CSS = """
    AgentFleetPanel {
        border: round $primary;
        border-title-color: $primary;
        border-title-style: bold;
        background: $surface;
        padding: 0;
        height: 100%;
    }
    AgentFleetPanel:focus-within {
        border: round $accent;
    }
    #agent-list {
        height: 100%;
        background: $surface;
    }
    ListView {
        height: 100%;
    }
    ListItem.--highlight {
        background: $panel;
    }
    """

    selected_agent: reactive[str | None] = reactive(None)
    _follow_latest: bool = True

    class AgentSelected(Message):
        def __init__(self, agent_id: str) -> None:
            self.agent_id = agent_id
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = "AGENT FLEET"
        self._agents: dict[str, AgentRow] = {}

    def compose(self) -> ComposeResult:
        yield ListView(id="agent-list")

    def upsert_agent(self, agent: AgentRow) -> None:
        self._agents[agent.name] = agent
        lv = self.query_one("#agent-list", ListView)
        
        # Check if agent already exists
        existing = lv.get_child_by_id(f"agent-{agent.name}")
        if existing:
            existing.remove()
        
        # Create new list item
        state = agent.state or "idle"
        role = agent.role or "unknown"
        runtime = agent.runtime or "—"
        task = (agent.task or "")[:35]
        state_icon = STATE_ICON.get(state, "○")
        role_icon = ROLE_ICONS.get(role.lower(), "🤖")
        
        label_text = f"{state_icon}  {role_icon} {agent.name:<14.14} {role:<10.10} {runtime:<10.10} {task}"
        item = ListItem(Label(label_text), id=f"agent-{agent.name}")
        lv.append(item)
        
        # Auto-select the newest agent
        if self._follow_latest:
            lv.index = len(lv.children) - 1
            self.selected_agent = agent.name
            self.post_message(self.AgentSelected(agent.name))

    def remove_agent(self, name: str) -> None:
        self._agents.pop(name, None)
        lv = self.query_one("#agent-list", ListView)
        existing = lv.get_child_by_id(f"agent-{name}")
        if existing:
            existing.remove()
        
        # If we removed the selected agent, clear selection
        if self.selected_agent == name:
            self.selected_agent = None

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle agent selection from ListView"""
        self._follow_latest = False   # user manually selected, stop following
        agent_id = event.item.id.removeprefix("agent-")
        self.selected_agent = agent_id
        self.post_message(self.AgentSelected(agent_id))

    def get_agent_count(self) -> int:
        return len(self._agents)

    def get_running_count(self) -> int:
        return sum(1 for a in self._agents.values() if a.state == "running")