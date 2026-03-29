"""
Anti-drift monitoring system for detecting role constraint violations.

This module monitors agent output for actions that violate role constraints,
such as file modifications by read-only roles or forbidden tool usage.

Extended with alert pipeline for supervisor notification.
"""

import re
import asyncio
from typing import Callable, List, Optional
from dataclasses import dataclass
from ..messaging.event_bus import event_bus


@dataclass
class DriftViolation:
    """Information about a detected role constraint violation."""

    role: str
    violation_type: str
    tool_line: str
    message: str


class DriftAlert:
    """An alert generated when drift violations accumulate."""

    def __init__(self, agent_name: str, role: str, violations: List[DriftViolation]):
        self.agent_name = agent_name
        self.role = role
        self.violations = violations
        self.severity = self._compute_severity()

    def _compute_severity(self) -> str:
        if len(self.violations) >= 3:
            return "critical"
        if len(self.violations) >= 1:
            return "warning"
        return "info"

    def summary(self) -> str:
        lines = [f"Drift alert [{self.severity}] for {self.agent_name} ({self.role}):"]
        for v in self.violations[:5]:
            lines.append(f"  - {v.message}")
        return "\n".join(lines)


class AntiDriftMonitor:
    """Monitors agent output for role constraint violations."""

    def __init__(self):
        self._event_callback: Optional[Callable] = None
        self._alert_callbacks: List[Callable] = []
        self._violation_history: dict[str, List[DriftViolation]] = {}
        self._alert_threshold = 3

        # Role-specific forbidden patterns
        self._role_constraints = {
            "scout": {
                "forbidden_tools": [r"\[write\]", r"\[edit\]", r"\[bash\]"],
                "description": "Scouts must not modify files or execute commands",
            },
            "reviewer": {
                "forbidden_tools": [r"\[write\]", r"\[edit\]", r"\[bash\]"],
                "description": "Reviewers must not modify files or execute commands",
            },
            "monitor": {
                "forbidden_tools": [r"\[write\]", r"\[edit\]"],
                "description": "Monitors must not modify files",
            },
            "tester": {
                "forbidden_tools": [r"git\s+(push|merge|rebase)", r"rm\s+-rf"],
                "description": "Testers must not push code or delete files",
            },
        }

    def set_event_callback(self, callback: Callable):
        """Set the event callback for emitting warnings."""
        self._event_callback = callback

    def register_alert_callback(self, callback: Callable) -> None:
        """Register a callback for drift alerts."""
        self._alert_callbacks.append(callback)

    async def monitor_output(
        self,
        last_output: str,
        agent_role: str,
        agent_name: str = "",
        session_id: Optional[str] = None,
    ) -> List[DriftViolation]:
        """
        Monitor agent output for role constraint violations.

        Args:
            last_output: The agent's output to analyze
            agent_role: The role of the agent producing the output
            agent_name: The name/ID of the agent
            session_id: Optional session ID for event correlation

        Returns:
            List of detected violations (empty if none found)
        """
        violations = []

        if agent_role not in self._role_constraints:
            return violations

        constraints = self._role_constraints[agent_role]

        for line in last_output.split("\n"):
            line = line.strip()
            if not line:
                continue

            # Check for forbidden tool patterns
            for pattern in constraints["forbidden_tools"]:
                if re.search(pattern, line, re.IGNORECASE):
                    violation = DriftViolation(
                        role=agent_role,
                        violation_type="tool_violation",
                        tool_line=line,
                        message=f"{agent_role} attempted forbidden action: {line}",
                    )
                    violations.append(violation)

                    # Emit warning via EventBus
                    await event_bus.emit(
                        event_type="drift",
                        source="anti-drift-monitor",
                        data={
                            "violation": violation.violation_type,
                            "tool": violation.tool_line,
                            "message": violation.message,
                            "severity": "high",
                            "agent_name": agent_name,
                        },
                        session_id=session_id,
                    )

                    # Also trigger legacy callback if present
                    if self._event_callback:
                        self._event_callback(
                            "warn",
                            agent_role,
                            f"Role constraint violation: {constraints['description']} - {line}",
                        )

                    break  # Only report first violation per line

        # Track violations and check for alert threshold
        if violations and agent_name:
            if agent_name not in self._violation_history:
                self._violation_history[agent_name] = []
            self._violation_history[agent_name].extend(violations)

            total = len(self._violation_history[agent_name])
            if total >= self._alert_threshold:
                alert = DriftAlert(
                    agent_name, agent_role, self._violation_history[agent_name]
                )
                self._fire_alert(alert)
                # Reset after alerting
                self._violation_history[agent_name] = []

        return violations

    def _fire_alert(self, alert: DriftAlert) -> None:
        """Fire alert to registered callbacks."""
        for callback in self._alert_callbacks:
            try:
                callback(alert)
            except Exception:
                pass

    def get_violation_count(self, agent_name: str) -> int:
        """Get total violation count for an agent."""
        return len(self._violation_history.get(agent_name, []))

    def add_role_constraints(
        self, role: str, forbidden_tools: List[str], description: str
    ):
        """Add or update role-specific constraints."""
        self._role_constraints[role] = {
            "forbidden_tools": forbidden_tools,
            "description": description,
        }

    def get_role_constraints(self, role: str) -> dict:
        """Get constraints for a specific role."""
        return self._role_constraints.get(role, {})


# Global instance for easy access
anti_drift_monitor = AntiDriftMonitor()
