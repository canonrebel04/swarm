"""
Base class for remote agent runtimes (SSH, Docker, etc.).
"""

from abc import abstractmethod
from typing import Optional
from .base import AgentRuntime, AgentConfig


class RemoteAgentRuntime(AgentRuntime):
    """Abstract base class for runtimes that execute on remote hosts or containers."""

    @abstractmethod
    async def sync_worktree(self, local_path: str, remote_path: str) -> bool:
        """
        Synchronize local worktree to the remote environment.
        
        Args:
            local_path: Path on the local machine
            remote_path: Path on the remote machine/container
            
        Returns:
            True if synchronization was successful
        """
        pass

    @abstractmethod
    async def fetch_results(self, remote_path: str, local_path: str) -> bool:
        """
        Fetch modified files from the remote environment back to local worktree.
        
        Args:
            remote_path: Path on the remote machine/container
            local_path: Path on the local machine
            
        Returns:
            True if fetching was successful
        """
        pass
