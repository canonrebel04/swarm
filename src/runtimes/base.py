"""
Base AgentRuntime interface for Swarm.

This module defines the core interface that all agent runtimes must implement,
along with the data structures for agent configuration and status tracking.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional


@dataclass
class AgentConfig:
    """Configuration for spawning a new agent."""
    name: str
    role: str
    task: str
    worktree_path: str
    model: str
    runtime: str
    system_prompt_path: str
    allowed_tools: list[str] = field(default_factory=list)
    blocked_tools: list[str] = field(default_factory=list)
    read_only: bool = False
    can_spawn_children: bool = False
    extra_env: dict[str, str] = field(default_factory=dict)


@dataclass
class AgentStatus:
    """Current status of an agent."""
    name: str
    role: str
    state: str  # queued | running | stalled | done | error | blocked
    current_task: str
    runtime: str
    last_output: str
    pid: Optional[int] = None


@dataclass
class RuntimeCapabilities:
    """Capabilities supported by a runtime."""
    interactive_chat: bool = False
    headless_run: bool = False
    resume_session: bool = False
    streaming_output: bool = False
    tool_allowlist: bool = False
    sandbox_support: bool = False
    agent_profiles: bool = False
    parallel_safe: bool = False


class AgentRuntime(ABC):
    """Abstract base class for all agent runtimes."""

    @property
    @abstractmethod
    def runtime_name(self) -> str:
        """Get the name of this runtime."""
        pass

    @property
    @abstractmethod
    def capabilities(self) -> RuntimeCapabilities:
        """Get the capabilities supported by this runtime."""
        pass

    @abstractmethod
    async def spawn(self, config: AgentConfig) -> str:
        """
        Spawn a new agent with the given configuration.
        
        Args:
            config: Agent configuration
            
        Returns:
            session_id: Unique identifier for this agent session
        """
        pass

    @abstractmethod
    async def send_message(self, session_id: str, message: str) -> None:
        """
        Send a message to an existing agent session.
        
        Args:
            session_id: Agent session identifier
            message: Message to send
        """
        pass

    @abstractmethod
    async def get_status(self, session_id: str) -> AgentStatus:
        """
        Get the current status of an agent session.
        
        Args:
            session_id: Agent session identifier
            
        Returns:
            Current agent status
        """
        pass

    @abstractmethod
    async def stream_output(self, session_id: str) -> AsyncIterator[str]:
        """
        Stream output from an agent session.
        
        Args:
            session_id: Agent session identifier
            
        Yields:
            Lines of output from the agent
        """
        pass

    @abstractmethod
    async def kill(self, session_id: str) -> None:
        """
        Terminate an agent session.
        
        Args:
            session_id: Agent session identifier
        """
        pass