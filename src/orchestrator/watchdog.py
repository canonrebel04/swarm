"""
Watchdog for monitoring agent health and detecting issues.

Extended with supervisor intervention workflow:
- Tracks drift violations per agent
- Escalates from nudge → warn → kill
- Fires supervisor alerts for manual review
"""

import asyncio
from typing import Dict, List, Callable, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from ..runtimes.base import AgentStatus
from .agent_manager import agent_manager


@dataclass
class AgentHealthState:
    """Tracks health state for a single agent."""

    name: str
    last_activity: datetime
    failed_nudges: int = 0
    drift_violations: int = 0
    last_violation: Optional[str] = None
    escalation_level: str = "normal"  # normal -> warned -> critical


class Watchdog:
    """Monitor agent health and detect stalled or problematic agents."""

    def __init__(self, stall_timeout: float = 120.0, check_interval: float = 10.0):
        self.stall_timeout = stall_timeout
        self.check_interval = check_interval
        self._agent_states: Dict[str, AgentHealthState] = {}
        self._monitoring = False
        self._monitor_task = None
        self._on_nudge_callbacks: List[Callable] = []
        self._on_respawn_callbacks: List[Callable] = []
        self._on_supervisor_alert_callbacks: List[Callable] = []

    async def start_monitoring(self):
        """Start monitoring agents."""
        if self._monitoring:
            return

        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self):
        """Stop monitoring agents."""
        if not self._monitoring:
            return

        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None

    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._monitoring:
            try:
                await self._check_agents()
            except Exception as e:
                print(f"Watchdog error: {e}")

            await asyncio.sleep(self.check_interval)

    async def _check_agents(self):
        """Check all agents for health issues."""
        agents = await agent_manager.list_agents()
        current_time = datetime.now()

        for agent in agents:
            state = self._get_or_create_state(agent.name)

            # Update last activity for active agents
            if agent.state in ["running", "queued"]:
                state.last_activity = current_time

            # Check for stalled agents
            time_since_activity = (current_time - state.last_activity).total_seconds()
            if time_since_activity > self.stall_timeout:
                await self._handle_stall(agent.name, state, time_since_activity)

    async def _handle_stall(
        self, agent_name: str, state: AgentHealthState, stall_time: float
    ) -> None:
        """Handle a stalled agent with escalation."""
        state.failed_nudges += 1

        if state.failed_nudges >= 6:
            # Critical: escalate to supervisor
            state.escalation_level = "critical"
            self._fire_supervisor_alert(
                agent_name,
                "critical_stall",
                f"Agent stalled for {stall_time:.0f}s with {state.failed_nudges} failed nudges",
            )
        elif state.failed_nudges >= 3:
            # Warned: respawn
            state.escalation_level = "warned"
            for callback in self._on_respawn_callbacks:
                try:
                    callback(agent_name, state.failed_nudges)
                except Exception:
                    pass
        else:
            # Normal: nudge
            for callback in self._on_nudge_callbacks:
                try:
                    callback(agent_name, stall_time)
                except Exception:
                    pass

    def record_drift_violation(self, agent_name: str, violation_detail: str) -> None:
        """Record a drift violation for an agent."""
        state = self._get_or_create_state(agent_name)
        state.drift_violations += 1
        state.last_violation = violation_detail

        if state.drift_violations >= 5:
            state.escalation_level = "critical"
            self._fire_supervisor_alert(
                agent_name,
                "drift_critical",
                f"{state.drift_violations} drift violations. Last: {violation_detail}",
            )
        elif state.drift_violations >= 3:
            state.escalation_level = "warned"
            self._fire_supervisor_alert(
                agent_name,
                "drift_warning",
                f"{state.drift_violations} drift violations detected",
            )

    def _get_or_create_state(self, agent_name: str) -> AgentHealthState:
        """Get or create health state for an agent."""
        if agent_name not in self._agent_states:
            self._agent_states[agent_name] = AgentHealthState(
                name=agent_name,
                last_activity=datetime.now(),
            )
        return self._agent_states[agent_name]

    def _fire_supervisor_alert(
        self, agent_name: str, alert_type: str, detail: str
    ) -> None:
        """Fire supervisor alert callbacks."""
        for callback in self._on_supervisor_alert_callbacks:
            try:
                callback(agent_name, alert_type, detail)
            except Exception:
                pass

    def register_nudge_callback(self, callback: Callable) -> None:
        """Register a callback to be called when an agent is nudged."""
        self._on_nudge_callbacks.append(callback)

    def register_respawn_callback(self, callback: Callable) -> None:
        """Register a callback to be called when an agent is respawned."""
        self._on_respawn_callbacks.append(callback)

    def register_supervisor_alert_callback(self, callback: Callable) -> None:
        """Register a callback for supervisor-level alerts."""
        self._on_supervisor_alert_callbacks.append(callback)

    async def register_agent_activity(self, agent_name: str):
        """Register that an agent has been active."""
        state = self._get_or_create_state(agent_name)
        state.last_activity = datetime.now()

    async def get_stalled_agents(self) -> List[str]:
        """Get list of potentially stalled agents."""
        stalled = []
        current_time = datetime.now()

        for name, state in self._agent_states.items():
            time_since = (current_time - state.last_activity).total_seconds()
            if time_since > self.stall_timeout:
                stalled.append(name)

        return stalled

    async def get_agent_health_report(self) -> Dict[str, str]:
        """Get health report for all agents."""
        report = {}
        current_time = datetime.now()

        agents = await agent_manager.list_agents()
        for agent in agents:
            state = self._agent_states.get(agent.name)
            if state:
                time_since = (current_time - state.last_activity).total_seconds()
                status = state.escalation_level
                if time_since <= self.stall_timeout:
                    status = "active"
                drift = (
                    f" drift={state.drift_violations}"
                    if state.drift_violations > 0
                    else ""
                )
                report[agent.name] = f"{status} ({time_since:.1f}s){drift}"
            else:
                report[agent.name] = "unknown"

        return report

    def get_escalation_level(self, agent_name: str) -> str:
        """Get current escalation level for an agent."""
        state = self._agent_states.get(agent_name)
        return state.escalation_level if state else "normal"

    def reset_agent(self, agent_name: str) -> None:
        """Reset health state for an agent (e.g., after successful nudge)."""
        if agent_name in self._agent_states:
            state = self._agent_states[agent_name]
            state.failed_nudges = 0
            state.drift_violations = 0
            state.escalation_level = "normal"
            state.last_violation = None


# Global watchdog instance
watchdog = Watchdog()
