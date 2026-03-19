"""
Agent Output Panel
"""

import re
import asyncio
from typing import Optional
from textual.app import ComposeResult
from textual.widgets import RichLog, Label
from textual.containers import Vertical
from textual import work


_ANSI = re.compile(r"\x1B(?:[@-Z\\-_]|\\[[0-?]*[ -/]*[@-~])")


class AgentOutputPanel(Vertical):
    _current: str | None = None
    _stream_task: Optional[work.Worker] = None
    
    @property
    def current_agent(self) -> str | None:
        return self._current

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
        try:
            log = self.query_one("#output-log", RichLog)
            log.clear()
            log.write(f"── {name} ──")
        except Exception:
            # Widget not mounted yet, skip
            pass

    def push_line(self, raw: str) -> None:
        clean = _ANSI.sub("", raw)[:4096]
        try:
            self.query_one("#output-log", RichLog).write(clean)
        except Exception:
            # Widget not mounted yet, skip
            pass

    def start_stream(self, agent_name: str) -> None:
        """Start streaming output for the selected agent."""
        # Cancel any existing stream
        if self._stream_task and not self._stream_task.done:
            self._stream_task.cancel()
        
        # Start new stream in a worker
        self._stream_task = self.run_worker(self._stream_agent_output(agent_name))

    @work(exclusive=True, thread=False)
    async def _stream_agent_output(self, agent_name: str) -> None:
        """Stream output from the selected agent."""
        try:
            # Get agent manager and registry from app (or use global instances for testing)
            if hasattr(self, 'app') and self.app:
                agent_manager = self.app.agent_manager
                registry = self.app.runtime_registry
            else:
                # Fallback for testing
                from ..orchestrator.agent_manager import agent_manager
            
            # Get session ID for this agent
            session_id = await agent_manager.get_session_id_by_name(agent_name)
            if not session_id:
                self.push_line(f"Agent {agent_name} not found")
                return
            
            # Get the runtime instance
            agent_info = None
            async with agent_manager._lock:
                agent_info = agent_manager._agents.get(session_id)
            
            if not agent_info:
                self.push_line(f"Agent {agent_name} not found in manager")
                return
            
            runtime_instance = agent_info.runtime_instance
            status = agent_info.status
            
            # Check if agent is done (no live process)
            if status.state in ["done", "error"]:
                # Replay from SQLite message bus
                self.push_line(f"Agent {agent_name} is {status.state} - replaying from message bus")
                # TODO: Implement DB replay when messaging system is available
                self.push_line(f"[Would replay last N lines from SQLite message bus for {agent_name}]")
            else:
                # Stream live output
                self.push_line(f"Streaming live output for {agent_name}...")
                try:
                    async for line in runtime_instance.stream_output(session_id):
                        self.push_line(line)
                except asyncio.CancelledError:
                    self.push_line(f"Stream cancelled for {agent_name}")
                except Exception as e:
                    self.push_line(f"Stream error for {agent_name}: {e}")
        
        except Exception as e:
            self.push_line(f"Error starting stream for {agent_name}: {e}")