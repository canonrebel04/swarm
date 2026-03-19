"""
PolyglotSwarm TUI Application
Main Textual application structure for the overseer + fleet interface
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from .screens.main import MainScreen
from .theme import POLYGLOT_CSS
from ..orchestrator.agent_manager import agent_manager
from ..tui.state import AgentRow


class PolyglotSwarmApp(App):
    CSS = POLYGLOT_CSS
    TITLE = "PolyglotSwarm  ◈  multi-agent runtime"
    SUB_TITLE = "v0.1"

    BINDINGS = [
        Binding("ctrl+q",       "quit",            "Quit",         priority=True),
        Binding("ctrl+k",       "kill_selected",   "Kill",         show=True),
        Binding("ctrl+r",       "retry_selected",  "Retry",        show=True),
        Binding("ctrl+i",       "inspect_role",    "Role",         show=True),
        Binding("tab",          "focus_next",      "Next",         show=True),
        Binding("shift+tab",    "focus_previous",  "Prev",         show=False),
        Binding("f1",           "toggle_dark",     "Theme",        show=False),
    ]

    selected_agent: str | None = None

    def on_mount(self) -> None:
        self.push_screen(MainScreen())
        
        # Register AgentManager callbacks to update the TUI
        def on_spawn(status):
            """Callback when an agent is spawned"""
            if hasattr(self, '_current_screen') and hasattr(self._current_screen, 'query'):
                fleet_panel = self._current_screen.query_one("#agent-fleet", None)
                if fleet_panel:
                    agent_row = AgentRow.from_agent_status(status)
                    self.call_from_thread(fleet_panel.upsert_agent, agent_row)
        
        def on_state_change(status):
            """Callback when an agent's state changes"""
            if hasattr(self, '_current_screen') and hasattr(self._current_screen, 'query'):
                fleet_panel = self._current_screen.query_one("#agent-fleet", None)
                if fleet_panel:
                    agent_row = AgentRow.from_agent_status(status)
                    self.call_from_thread(fleet_panel.upsert_agent, agent_row)
        
        def on_kill(status):
            """Callback when an agent is killed"""
            if hasattr(self, '_current_screen') and hasattr(self._current_screen, 'query'):
                fleet_panel = self._current_screen.query_one("#agent-fleet", None)
                if fleet_panel:
                    self.call_from_thread(fleet_panel.remove_agent, status.name)
        
        # Register the callbacks
        agent_manager.register_spawn_callback(on_spawn)
        agent_manager.register_state_change_callback(on_state_change)
        agent_manager.register_kill_callback(on_kill)