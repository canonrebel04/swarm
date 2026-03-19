"""
Simple echo runtime for testing purposes.

This is a minimal implementation that echoes back messages for testing
the runtime system without requiring external dependencies.
"""

import asyncio
import uuid
from typing import AsyncIterator
from .base import AgentRuntime, AgentConfig, AgentStatus, RuntimeCapabilities


class EchoRuntime(AgentRuntime):
    """A simple echo runtime for testing."""

    def __init__(self):
        self._sessions = {}

    @property
    def runtime_name(self) -> str:
        return "echo"

    @property
    def capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            interactive_chat=True,
            headless_run=True,
            streaming_output=True,
            tool_allowlist=False,
            sandbox_support=False,
            agent_profiles=False,
            parallel_safe=True
        )

    async def spawn(self, config: AgentConfig) -> str:
        """Spawn a new echo agent."""
        session_id = str(uuid.uuid4())
        
        # Store session info
        self._sessions[session_id] = {
            'config': config,
            'status': AgentStatus(
                name=config.name,
                role=config.role,
                state="running",
                current_task=config.task,
                runtime=self.runtime_name,
                last_output="",
                pid=None
            ),
            'message_queue': asyncio.Queue()
        }
        
        # Start a background task to simulate agent output
        asyncio.create_task(self._simulate_agent_output(session_id))
        
        return session_id

    async def _simulate_agent_output(self, session_id: str):
        """Simulate agent output for testing."""
        if session_id not in self._sessions:
            return
        
        session = self._sessions[session_id]
        config = session['config']
        
        # Simulate some initial output
        await asyncio.sleep(0.1)
        await session['message_queue'].put(f"Agent {config.name} started")
        await session['message_queue'].put(f"Task: {config.task}")
        await session['message_queue'].put(f"Role: {config.role}")
        
        # Update status
        session['status'].last_output = "Agent started and ready"

    async def send_message(self, session_id: str, message: str) -> None:
        """Send a message to the echo agent."""
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self._sessions[session_id]
        
        # Echo the message back to the output queue
        echo_response = f"Echo: {message}"
        await session['message_queue'].put(echo_response)
        
        # Update status
        session['status'].last_output = echo_response

    async def get_status(self, session_id: str) -> AgentStatus:
        """Get the current status of an agent."""
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")
        
        return self._sessions[session_id]['status']

    async def stream_output(self, session_id: str) -> AsyncIterator[str]:
        """Stream output from the echo agent."""
        if session_id not in self._sessions:
            raise ValueError(f"Session {session_id} not found")
        
        session = self._sessions[session_id]
        queue = session['message_queue']
        
        while True:
            try:
                # Wait for messages with timeout to allow cleanup
                message = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield message
                queue.task_done()
            except asyncio.Timeout:
                # Check if session is still active
                if session_id not in self._sessions:
                    break
                continue

    async def kill(self, session_id: str) -> None:
        """Terminate an echo agent."""
        if session_id in self._sessions:
            # Update status to show agent was killed
            session = self._sessions[session_id]
            session['status'].state = "error"
            session['status'].last_output = "Agent terminated"
            
            # Clean up session
            del self._sessions[session_id]

    async def _set_state(self, session_id: str, state: str) -> None:
        """Set the state of an agent (for testing purposes)."""
        if session_id in self._sessions:
            session = self._sessions[session_id]
            session['status'].state = state
            session['status'].last_output = f"State changed to {state}"


# Register the echo runtime
def register_echo_runtime():
    """Register the echo runtime with the global registry."""
    from .registry import registry
    registry.register(EchoRuntime)


# Auto-register when imported
register_echo_runtime()