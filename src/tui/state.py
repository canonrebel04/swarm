"""
TUI State Definitions
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class AgentRow:
    """Represents a single agent in the fleet table"""
    name: str
    role: str
    state: str
    task: str
    runtime: str
    pid: Optional[int] = None
    
    @classmethod
    def from_agent_status(cls, status: 'AgentStatus') -> 'AgentRow':
        """Create an AgentRow from an AgentStatus"""
        return cls(
            name=status.name,
            role=status.role,
            state=status.state,
            task=status.current_task,
            runtime=status.runtime,
            pid=status.pid
        )
