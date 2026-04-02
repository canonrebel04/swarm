"""
PolyglotSwarm TUI Application
Main Textual application structure for the overseer + fleet interface
"""

from textual.app import App, ComposeResult
from textual.binding import Binding
from .screens.main import MainScreen
from .screens.confirm import ConfirmModal
from .screens.inspect import InspectModal
from .theme import POLYGLOT_CSS, SWARM_THEME
from ..orchestrator.agent_manager import agent_manager
from ..runtimes.registry import registry
from ..tui.state import AgentRow
import asyncio
import time


class SwarmApp(App):
    CSS = POLYGLOT_CSS
    TITLE = "Swarm  ◈  multi-agent runtime"
    SUB_TITLE = "v0.1"
    THEME = SWARM_THEME

    BINDINGS = [
        Binding("ctrl+q",       "quit",            "Quit",         priority=True),
        Binding("ctrl+k",       "kill_selected",   "Kill",         show=True),
        Binding("ctrl+r",       "retry_selected",  "Retry",        show=True),
        Binding("ctrl+n",       "new_chat",         "New Chat",     show=True),
        Binding("f2",       "model_selector",  "Model",        show=True),
        Binding("ctrl+s",       "skill_browser",   "Skills",       show=True),
        Binding("ctrl+i",       "inspect_role",    "Role",         show=True),
        Binding("tab",          "focus_next",      "Next",         show=True),
        Binding("shift+tab",    "focus_previous",  "Prev",         show=False),
        Binding("f1",           "toggle_dark",     "Theme",        show=False),
    ]

    selected_agent: str | None = None
    agent_manager = agent_manager
    runtime_registry = registry
    coordinator = None  # Will be set in _register_agent_manager_callbacks
    _start_time: float = 0.0

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
        # Initialize start time for clock
        self._start_time = time.monotonic()
        # Start live clock updates
        self._start_clock()
        # Register callbacks after screen is pushed to ensure DOM is ready
        self.set_timer(0.05, self._register_agent_manager_callbacks)
        # Autofocus overseer chat input after screen is ready
        self.set_timer(0.1, self._focus_chat_input)

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
        
        # Link coordinator to TaskGraph panel
        if hasattr(self, '_current_screen') and hasattr(self._current_screen, 'query'):
            graph_panel = self._current_screen.query_one("#task-graph", None)
            if graph_panel:
                graph_panel.coordinator = coordinator
        
        # Push startup event
        role_count = len(self.runtime_registry.list_roles())
        runtime_count = len(self.runtime_registry.list_runtimes())
        self.push_swarm_event("info", "system", f"Swarm initialized ◈ {role_count} roles loaded ◈ {runtime_count} runtimes available")
        
        print(f"DEBUG: Agent manager callbacks registered, start_time: {self._start_time}")
    

    
    # Action methods for keybindings
    
    async def action_kill_selected(self) -> None:
        """Kill the selected agent after confirmation."""
        if not self.selected_agent:
            return
        
        # Show confirmation dialog
        def handle_confirm(result: str) -> None:
            if result == "yes":
                self._kill_agent_confirmed(self.selected_agent)
        
        self.push_screen(ConfirmModal(f"Kill agent {self.selected_agent}?"), handle_confirm)
    
    async def _kill_agent_confirmed(self, agent_name: str) -> None:
        """Actually kill the agent after confirmation."""
        try:
            # Find the agent's session ID
            session_id = None
            async with self.agent_manager._lock:
                for agent_info in self.agent_manager._agents.values():
                    if agent_info.status.name == agent_name:
                        session_id = agent_info.session_id
                        break
            
            if session_id:
                await self.agent_manager.kill(session_id)
                self.push_swarm_event("kill", agent_name, "terminated by user")
        except Exception as e:
            self.push_swarm_event("error", "system", f"Failed to kill agent: {e}")
    
    async def action_retry_selected(self) -> None:
        """Retry the selected agent."""
        if not self.selected_agent:
            return
        
        try:
            # Check if agent is still running
            agents = await self.agent_manager.list_agents()
            for agent in agents:
                if agent.name == self.selected_agent and agent.state in ["running", "queued"]:
                    self.push_swarm_event("error", self.selected_agent, "cannot retry — agent still running")
                    return
            
            # Find the original config
            original_config = None
            async with self.agent_manager._lock:
                for agent_info in self.agent_manager._agents.values():
                    if agent_info.status.name == self.selected_agent:
                        original_config = agent_info.config
                        break
            
            if original_config:
                # Spawn new agent with same config
                await self.agent_manager.spawn_agent(original_config.runtime, original_config)
                self.push_swarm_event("spawn", self.selected_agent, "retried by user")
            else:
                self.push_swarm_event("error", self.selected_agent, "cannot retry — original config not found")
        except Exception as e:
            self.push_swarm_event("error", "system", f"Failed to retry agent: {e}")

    def action_new_chat(self) -> None:
        """Clear the current chat session."""
        chat = self.query_one("OverseerChatPanel")
        chat.query_one("#chat-scroll").remove_children()
        self.notify("Chat session cleared", severity="information")
    
    def action_skill_browser(self) -> None:
        """Open the skill browser modal."""
        from src.tui.screens.skills import SkillBrowserModal
        self.push_screen(SkillBrowserModal())

    async def action_inspect_role(self) -> None:
        """Inspect the selected agent's role contract and identity."""
        if not self.selected_agent:
            return
        
        try:
            # Get the agent's role
            agent_role = None
            agents = await self.agent_manager.list_agents()
            for agent in agents:
                if agent.name == self.selected_agent:
                    agent_role = agent.role
                    break
            
            if agent_role:
                # Load the role contract (YAML)
                yaml_path = f"src/roles/contracts/{agent_role}.yaml"
                yaml_content = ""
                if os.path.exists(yaml_path):
                    with open(yaml_path, 'r') as f:
                        yaml_content = f.read()
                else:
                    yaml_content = f"# No YAML contract found at {yaml_path}"

                # Load the role identity (MD)
                md_path = f"src/agents/definitions/{agent_role}.md"
                md_content = ""
                if os.path.exists(md_path):
                    with open(md_path, 'r') as f:
                        md_content = f.read()
                else:
                    md_content = f"# No Markdown definition found at {md_path}"
                
                # Show enhanced inspect modal
                self.push_screen(InspectModal(self.selected_agent, agent_role, yaml_content, md_content))
        except Exception as e:
            self.push_swarm_event("error", "system", f"Failed to inspect role: {e}")

    def handle_overseer_input(self, text: str) -> None:
        """Handle overseer input from the chat panel."""
        if not hasattr(self, 'coordinator') or self.coordinator is None:
            self.push_swarm_event("error", "system", "Coordinator not initialized")
            return
        
        try:
            # Add the message to chat history
            chat_panel = self.query_one("OverseerChatPanel")
            chat_panel.add_message("overseer", f"Processing: {text}")
            
            # Pass to coordinator for task decomposition
            self.coordinator.handle_overseer_input(text)
            
            # Push event
            self.push_swarm_event("info", "overseer", f"received: {text}")
        except Exception as e:
            self.push_swarm_event("error", "system", f"Failed to process overseer input: {e}")
    
    def on_agent_fleet_panel_agent_selected(self, message: "AgentFleetPanel.AgentSelected") -> None: # type: ignore
        """Handle agent selection from the fleet panel."""
        self.selected_agent = message.agent_id
        # Update the output panel to show the selected agent's output
        output_panel = self.query_one("AgentOutputPanel")
        if output_panel:
            output_panel.set_agent(message.agent_id)

    def _start_clock(self) -> None:
        """Start the live clock updates."""
        # Use set_interval for reliable 1-second updates
        self.set_interval(1.0, self._update_statusbar)

    def _focus_chat_input(self) -> None:
        """Focus the overseer chat input so the user can type immediately."""
        try:
            from src.tui.panels.overseer_chat import OverseerChatPanel
            panel = self.query_one(OverseerChatPanel)
            # Try common input widget IDs — adjust to match your actual widget id
            for selector in ("#chat-input", "#overseer-input", "Input"):
                try:
                    panel.query_one(selector).focus()
                    return
                except Exception:
                    continue
        except Exception:
            pass

    def _update_statusbar(self) -> None:
        """Update the statusbar with live agent count and clock."""
        try:
            count = len(self.agent_manager._agents) if self.agent_manager else 0
            runtime = "vibe"  # Default runtime
            
            # Calculate elapsed time from start
            elapsed_seconds = int(time.monotonic() - self._start_time)
            hours, remainder = divmod(elapsed_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            elapsed = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            # Update statusbar via screen method
            if hasattr(self, '_current_screen') and hasattr(self._current_screen, 'update_statusbar'):
                self._current_screen.update_statusbar(count, runtime, elapsed)
        except Exception as e:
            # Don't let statusbar updates break the application
            pass

    def action_model_selector(self) -> None:
        """Open the model selector modal."""
        from src.tui.screens.model_selector import ModelSelectorModal

        def handle_result(result: dict | None) -> None:
            if result:
                runtime = result["runtime"]
                model   = result["model"]
                self.notify(f"Overseer: {runtime} / {model}", title="Model updated")
                # Live-reload the coordinator with new config if running
                if hasattr(self, "coordinator"):
                    self.coordinator.reload_model(runtime, model)

        self.push_screen(ModelSelectorModal(), handle_result)