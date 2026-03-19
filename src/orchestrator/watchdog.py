"""
Watchdog for monitoring agent health and detecting issues.
"""

import asyncio
from typing import Dict, List
from datetime import datetime, timedelta
from ..runtimes.base import AgentStatus
from .agent_manager import agent_manager


class Watchdog:
    """Monitor agent health and detect stalled or problematic agents."""

    def __init__(self, stall_timeout: float = 120.0, check_interval: float = 10.0):
        self.stall_timeout = stall_timeout
        self.check_interval = check_interval
        self._last_activity: Dict[str, datetime] = {}
        self._monitoring = False
        self._monitor_task = None
        self._on_nudge_callbacks = []
        self._on_respawn_callbacks = []

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
            session_id = None
            # Find session_id for this agent (we need to track this better)
            # For now, we'll just check the agents we know about
            
            # Update last activity for active agents
            if agent.state in ["running", "queued"]:
                self._last_activity[agent.name] = current_time
            
            # Check for stalled agents
            last_activity = self._last_activity.get(agent.name)
            if last_activity:
                time_since_activity = (current_time - last_activity).total_seconds()
                if time_since_activity > self.stall_timeout:
                    print(f"⚠️  Agent {agent.name} appears stalled (no activity for {time_since_activity:.1f}s)")
                    # Trigger nudge callbacks
                    for callback in self._on_nudge_callbacks:
                        try:
                            callback(agent.name, time_since_activity)
                        except Exception:
                            pass  # Don't let callback failures break the watchdog
                    
                    # Nudge the agent (in a real implementation, this would send a signal)
                    print(f"🔄  Nudging agent {agent.name}")
                    
                    # Track failed nudges and potentially respawn
                    failed_nudges = getattr(agent, 'failed_nudges', 0) + 1
                    if failed_nudges >= 3:  # Respawn after 3 failed nudges
                        print(f"🔥  Respawn agent {agent.name} after {failed_nudges} failed nudges")
                        # Trigger respawn callback
                        for callback in self._on_respawn_callbacks:
                            try:
                                callback(agent.name, failed_nudges)
                            except Exception:
                                pass  # Don't let callback failures break the watchdog
                        
                        # Reset nudge counter
                        failed_nudges = 0
                    
                    # Update agent with failed nudge count (simulated)
                    agent.failed_nudges = failed_nudges

    def register_nudge_callback(self, callback):
        """Register a callback to be called when an agent is nudged."""
        self._on_nudge_callbacks.append(callback)

    def register_respawn_callback(self, callback):
        """Register a callback to be called when an agent is respawned."""
        self._on_respawn_callbacks.append(callback)

    async def register_agent_activity(self, agent_name: str):
        """Register that an agent has been active."""
        self._last_activity[agent_name] = datetime.now()

    async def get_stalled_agents(self) -> List[str]:
        """Get list of potentially stalled agents."""
        stalled = []
        current_time = datetime.now()
        
        for agent_name, last_activity in self._last_activity.items():
            time_since_activity = (current_time - last_activity).total_seconds()
            if time_since_activity > self.stall_timeout:
                stalled.append(agent_name)
        
        return stalled

    async def get_agent_health_report(self) -> Dict[str, str]:
        """Get health report for all agents."""
        report = {}
        current_time = datetime.now()
        
        agents = await agent_manager.list_agents()
        for agent in agents:
            last_activity = self._last_activity.get(agent.name)
            if last_activity:
                time_since_activity = (current_time - last_activity).total_seconds()
                status = "active" if time_since_activity <= self.stall_timeout else "stalled"
                report[agent.name] = f"{status} ({time_since_activity:.1f}s)"
            else:
                report[agent.name] = "unknown"
        
        return report


# Global watchdog instance
watchdog = Watchdog()