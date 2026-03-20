"""
Anti-drift monitoring system for detecting role constraint violations.

This module monitors agent output for actions that violate role constraints,
such as file modifications by read-only roles or forbidden tool usage.
"""

import re
from typing import Callable, List, Optional
from dataclasses import dataclass


@dataclass
class DriftViolation:
    """Information about a detected role constraint violation."""
    role: str
    violation_type: str
    tool_line: str
    message: str


class AntiDriftMonitor:
    """Monitors agent output for role constraint violations."""
    
    def __init__(self):
        self._event_callback: Optional[Callable] = None
        
        # Role-specific forbidden patterns
        self._role_constraints = {
            'scout': {
                'forbidden_tools': [r'\[write\]', r'\[edit\]', r'\[bash\]'],
                'description': 'Scouts must not modify files or execute commands'
            },
            'reviewer': {
                'forbidden_tools': [r'\[write\]', r'\[edit\]', r'\[bash\]'],
                'description': 'Reviewers must not modify files or execute commands'
            },
            'monitor': {
                'forbidden_tools': [r'\[write\]', r'\[edit\]'],
                'description': 'Monitors must not modify files'
            },
            'tester': {
                'forbidden_tools': [r'git\s+(push|merge|rebase)', r'rm\s+-rf'],
                'description': 'Testers must not push code or delete files'
            }
        }
    
    def set_event_callback(self, callback: Callable):
        """Set the event callback for emitting warnings."""
        self._event_callback = callback
    
    def monitor_output(self, last_output: str, agent_role: str) -> List[DriftViolation]:
        """
        Monitor agent output for role constraint violations.
        
        Args:
            last_output: The agent's output to analyze
            agent_role: The role of the agent producing the output
            
        Returns:
            List of detected violations (empty if none found)
        """
        violations = []
        
        if agent_role not in self._role_constraints:
            return violations
        
        constraints = self._role_constraints[agent_role]
        
        for line in last_output.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Check for forbidden tool patterns
            for pattern in constraints['forbidden_tools']:
                if re.search(pattern, line, re.IGNORECASE):
                    violation = DriftViolation(
                        role=agent_role,
                        violation_type='tool_violation',
                        tool_line=line,
                        message=f"{agent_role} attempted forbidden action: {line}"
                    )
                    violations.append(violation)
                    
                    # Emit warning event
                    if self._event_callback:
                        self._event_callback(
                            "warn", agent_role, 
                            f"Role constraint violation: {constraints['description']} - {line}"
                        )
                    
                    break  # Only report first violation per line
        
        return violations
    
    def add_role_constraints(self, role: str, forbidden_tools: List[str], description: str):
        """Add or update role-specific constraints."""
        self._role_constraints[role] = {
            'forbidden_tools': forbidden_tools,
            'description': description
        }
    
    def get_role_constraints(self, role: str) -> dict:
        """Get constraints for a specific role."""
        return self._role_constraints.get(role, {})


# Global instance for easy access
anti_drift_monitor = AntiDriftMonitor()
