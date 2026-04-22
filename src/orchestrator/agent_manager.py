"""
Agent manager for tracking and managing active agents.
"""

from typing import Dict, List, Optional, AsyncIterator
from dataclasses import dataclass
import asyncio
import uuid
from ..runtimes.base import AgentConfig, AgentStatus
from ..runtimes.registry import registry
from ..safety.anti_drift import anti_drift_monitor


@dataclass
class AgentInfo:
    """Information about an active agent."""
    session_id: str
    config: AgentConfig
    status: AgentStatus
    runtime_instance: object
    created_at: float
    last_updated: float


class AgentManager:
    """Manage the fleet of active agents."""

    def __init__(self):
        self._agents: Dict[str, AgentInfo] = {}
        self._lock = asyncio.Lock()
        self._on_spawn_callbacks = []
        self._on_state_change_callbacks = []
        self._on_kill_callbacks = []

    def register_spawn_callback(self, callback):
        """Register a callback to be called when an agent is spawned."""
        self._on_spawn_callbacks.append(callback)

    def register_state_change_callback(self, callback):
        """Register a callback to be called when an agent's state changes."""
        self._on_state_change_callbacks.append(callback)

    def register_kill_callback(self, callback):
        """Register a callback to be called when an agent is killed."""
        self._on_kill_callbacks.append(callback)

    async def spawn_agent(self, config: AgentConfig) -> str:
        """
        Spawn a new agent with the given configuration.
        
        Args:
            config: Agent configuration
            
        Returns:
            session_id: Unique identifier for the agent session
        """
        runtime_class = registry.get(config.runtime)
        if not runtime_class:
            raise ValueError(f"Runtime {config.runtime} not found")
        
        runtime_instance = runtime_class()
        session_id = await runtime_instance.spawn(config)
        
        # Create agent info
        agent_info = AgentInfo(
            session_id=session_id,
            config=config,
            status=AgentStatus(
                name=config.name,
                role=config.role,
                state="running",
                current_task=config.task,
                runtime=config.runtime,
                last_output="",
                pid=None
            ),
            runtime_instance=runtime_instance,
            created_at=asyncio.get_event_loop().time(),
            last_updated=asyncio.get_event_loop().time()
        )
        
        async with self._lock:
            self._agents[session_id] = agent_info
        
        # Call spawn callbacks
        for callback in self._on_spawn_callbacks:
            try:
                callback(agent_info.status)
            except Exception:
                pass  # Don't let callback failures break the spawn
        
        return session_id

    async def get_agent_status(self, session_id: str) -> Optional[AgentStatus]:
        """
        Get the current status of an agent.
        
        Args:
            session_id: Agent session identifier
            
        Returns:
            Current agent status or None if not found
        """
        # ⚡ Bolt Optimization: Only hold the lock to retrieve the agent_info object
        # to avoid blocking the event loop while awaiting the I/O-bound get_status method.
        async with self._lock:
            agent_info = self._agents.get(session_id)
            if not agent_info:
                return None
            
        # Get fresh status from runtime outside the lock
        try:
            fresh_status = await agent_info.runtime_instance.get_status(session_id)

            # Re-acquire lock to update the internal state safely
            async with self._lock:
                # Double check the agent hasn't been deleted while we were yielding
                if session_id not in self._agents:
                    return fresh_status
                
                # Check if state actually changed inside the lock to prevent race conditions
                state_changed = fresh_status.state != agent_info.status.state

                agent_info.status = fresh_status
                agent_info.last_updated = asyncio.get_event_loop().time()

            # Call state change callbacks outside the lock to prevent re-entrancy issues
            if state_changed:
                for callback in self._on_state_change_callbacks:
                    try:
                        callback(fresh_status)
                    except Exception:
                        pass  # Don't let callback failures break status updates

            return fresh_status
        except Exception:
            return agent_info.status

    async def send_message(self, session_id: str, message: str) -> bool:
        """
        Send a message to an agent.
        
        Args:
            session_id: Agent session identifier
            message: Message to send
            
        Returns:
            True if successful, False if agent not found
        """
        async with self._lock:
            agent_info = self._agents.get(session_id)
            if not agent_info:
                return False
            
            try:
                await agent_info.runtime_instance.send_message(session_id, message)
                return True
            except Exception:
                return False

    async def kill_agent(self, session_id: str) -> bool:
        """
        Terminate an agent.
        
        Args:
            session_id: Agent session identifier
            
        Returns:
            True if successful, False if agent not found
        """
        async with self._lock:
            agent_info = self._agents.get(session_id)
            if not agent_info:
                return False
            
            try:
                await agent_info.runtime_instance.kill(session_id)
                
                # Call kill callbacks before removing from agents dict
                for callback in self._on_kill_callbacks:
                    try:
                        callback(agent_info.status)
                    except Exception:
                        pass  # Don't let callback failures break the kill
                
                del self._agents[session_id]
                return True
            except Exception:
                return False

    async def stream_agent_output(self, session_id: str) -> AsyncIterator[str]:
        """
        Stream output from an agent.
        
        Args:
            session_id: Agent session identifier
            
        Yields:
            Lines of output from the agent
        """
        # Get agent info outside the loop to avoid holding lock while yielding
        async with self._lock:
            agent_info = self._agents.get(session_id)
            if not agent_info:
                return

        try:
            async for line in agent_info.runtime_instance.stream_output(session_id):
                # Check for drift violations
                await anti_drift_monitor.monitor_output(
                    line, agent_info.config.role, session_id
                )
                yield line
        except Exception as e:
            yield f"Error streaming output: {e}"

    async def list_agents(self) -> List[AgentStatus]:
        """
        List all active agents.
        
        Returns:
            List of agent statuses
        """
        async with self._lock:
            return [agent.status for agent in self._agents.values()]

    async def get_agent_count(self) -> int:
        """
        Get the number of active agents.
        
        Returns:
            Number of active agents
        """
        async with self._lock:
            return len(self._agents)

    async def get_session_id_by_name(self, agent_name: str) -> Optional[str]:
        """
        Get session ID for an agent by name.
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            Session ID if found, None otherwise
        """
        async with self._lock:
            for session_id, agent_info in self._agents.items():
                if agent_info.status.name == agent_name:
                    return session_id
            return None

    async def cleanup_all(self) -> None:
        """Terminate all active agents."""
        # Make a copy of the keys to avoid modifying dict during iteration
        session_ids = list(self._agents.keys())
        
        for session_id in session_ids:
            try:
                await self.kill_agent(session_id)
            except Exception:
                # Continue with cleanup even if individual agents fail
                pass


# Global agent manager instance
agent_manager = AgentManager()
