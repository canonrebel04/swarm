"""
Main TUI Screen
"""

from textual.screen import Screen
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer
from ..panels.overseer_chat import OverseerChatPanel
from ..panels.agent_fleet import AgentFleetPanel
from ..panels.agent_output import AgentOutputPanel
from ..panels.event_log import EventLogPanel


class MainScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="layout"):
            with Vertical(id="left-col"):
                yield OverseerChatPanel(id="overseer-chat")
            with Vertical(id="right-col"):
                yield AgentFleetPanel(id="agent-fleet")
                with Horizontal(id="output-row"):
                    yield AgentOutputPanel(id="agent-output")
                    yield EventLogPanel(id="event-log")
        yield Footer()