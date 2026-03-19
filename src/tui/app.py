"""
PolyglotSwarm TUI Application
Main Textual application structure for the overseer + fleet interface
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from .screens.main import MainScreen
from .theme import POLYGLOT_CSS
from ..orchestrator.agent_manager import agent_manager
from ..runtimes.registry import registry
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
    agent_manager = agent_manager
    runtime_registry = registry
    coordinator = None  # Will be set in _register_agent_manager_callbacks

    def push_swarm_event(self, level: str, source: str, message: str) -> None:
        """Push an event to the event log panel safely from any context."""
        try:
            if hasattr(self, '_current_screen') and hasattr(self._current_screen, 'query'):
                event_panel = self._current_screen.query_one("#event-log", None)
                if event_panel and hasattr(event_panel, 'push_event'):
                    self.call_later(event_panel.push_event, level, source, message)
        except Exception as e:
            # Don't let event logging break the application
            print(f"Error pushing event: {e}")

    def on_mount(self) -> None:
        self.push_screen(MainScreen())
        # Register callbacks after screen is pushed to ensure DOM is ready
        self.set_timer(0.05, self._register_agent_manager_callbacks)

    def _register_agent_manager_callbacks(self) -> None:
        """Register AgentManager callbacks after screen is mounted."""
        def on_spawn(status):
            """Callback when an agent is spawned"""
            if hasattr(self, '_current_screen') and hasattr(self._current_screen, 'query'):
                fleet_panel = self._current_screen.query_one("#agent-fleet", None)
                if fleet_panel:
                    agent_row = AgentRow.from_agent_status(status)
                    self.call_later(fleet_panel.upsert_agent, agent_row)
            
            # Push spawn event
            self.push_swarm_event("spawn", status.name, f"spawned as {status.role} on {status.runtime}")
        
        def on_state_change(status):
            """Callback when an agent's state changes"""
            if hasattr(self, '_current_screen') and hasattr(self._current_screen, 'query'):
                fleet_panel = self._current_screen.query_one("#agent-fleet", None)
                if fleet_panel:
                    agent_row = AgentRow.from_agent_status(status)
                    self.call_later(fleet_panel.upsert_agent, agent_row)
            
            # Push state change events
            if status.state == "stalled":
                self.push_swarm_event("warn", status.name, "stalled — watchdog will nudge")
            elif status.state == "done":
                self.push_swarm_event("done", status.name, "completed task")
            elif status.state == "error":
                self.push_swarm_event("error", status.name, "exited with error")
        
        def on_kill(status):
            """Callback when an agent is killed"""
            if hasattr(self, '_current_screen') and hasattr(self._current_screen, 'query'):
                fleet_panel = self._current_screen.query_one("#agent-fleet", None)
                if fleet_panel:
                    self.call_later(fleet_panel.remove_agent, status.name)
            
            # Push kill event
            self.push_swarm_event("kill", status.name, "terminated")
        
        # Register the callbacks
        agent_manager.register_spawn_callback(on_spawn)
        agent_manager.register_state_change_callback(on_state_change)
        agent_manager.register_kill_callback(on_kill)
        
        # Register Watchdog callbacks
        def on_watchdog_nudge(agent_name, stall_time):
            self.push_swarm_event("warn", agent_name, f"nudged after {stall_time:.1f}s stall")
        
        def on_watchdog_respawn(agent_name, failed_nudges):
            self.push_swarm_event("warn", agent_name, f"respawned after {failed_nudges} failed nudges")
        
        from ..orchestrator.watchdog import watchdog
        watchdog.register_nudge_callback(on_watchdog_nudge)
        watchdog.register_respawn_callback(on_watchdog_respawn)
        
        # Register Coordinator callbacks and event callback
        def on_task_assigned(task_packet):
            self.push_swarm_event("info", "coordinator", f"→ {task_packet.role_required}: {task_packet.title}")
        
        def on_handoff(from_agent, to_role, task_title):
            self.push_swarm_event("info", from_agent, f"handoff → {to_role}")
        
        def push_coordinator_event(level, source, message):
            self.push_swarm_event(level, source, message)
        
        from ..orchestrator.coordinator import coordinator
        coordinator.register_task_assigned_callback(on_task_assigned)
        coordinator.register_handoff_callback(on_handoff)
        coordinator.register_event_callback(push_coordinator_event)
        
        # Store coordinator reference for chat panel access
        self.coordinator = coordinator
        
        # Push startup event
        role_count = len(self.runtime_registry.list_roles())
        runtime_count = len(self.runtime_registry.list_runtimes())
        self.push_swarm_event("info", "system", f"PolyglotSwarm initialized ◈ {role_count} roles loaded ◈ {runtime_count} runtimes available")