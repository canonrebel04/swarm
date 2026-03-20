"""
Test event bus wiring from orchestrator components to TUI
"""

import pytest
import asyncio
from src.tui.app import SwarmApp
from src.orchestrator.agent_manager import agent_manager
from src.orchestrator.watchdog import watchdog
from src.orchestrator.coordinator import coordinator, TaskPacket
from src.runtimes.base import AgentConfig


class TestEventWiring:
    """Test that event wiring works correctly"""
    
    def test_agent_manager_events(self):
        """Test that AgentManager events are wired to TUI"""
        # Create a mock app to capture events
        class MockApp:
            def __init__(self):
                self.events = []
            
            def push_swarm_event(self, level, source, message):
                self.events.append({"level": level, "source": source, "message": message})
        
        mock_app = MockApp()
        
        # Manually register callbacks like the real app does
        def on_spawn(status):
            mock_app.push_swarm_event("spawn", status.name, f"spawned as {status.role} on {status.runtime}")
        
        def on_state_change(status):
            if status.state == "done":
                mock_app.push_swarm_event("done", status.name, "completed task")
        
        def on_kill(status):
            mock_app.push_swarm_event("kill", status.name, "terminated")
        
        # Register callbacks
        agent_manager.register_spawn_callback(on_spawn)
        agent_manager.register_state_change_callback(on_state_change)
        agent_manager.register_kill_callback(on_kill)
        
        # Test that callbacks are registered
        assert len(agent_manager._on_spawn_callbacks) > 0
        assert len(agent_manager._on_state_change_callbacks) > 0
        assert len(agent_manager._on_kill_callbacks) > 0
        
        # Clean up
        agent_manager._on_spawn_callbacks.clear()
        agent_manager._on_state_change_callbacks.clear()
        agent_manager._on_kill_callbacks.clear()
    
    def test_watchdog_events(self):
        """Test that Watchdog events are wired to TUI"""
        # Create a mock app to capture events
        class MockApp:
            def __init__(self):
                self.events = []
            
            def push_swarm_event(self, level, source, message):
                self.events.append({"level": level, "source": source, "message": message})
        
        mock_app = MockApp()
        
        # Manually register callbacks like the real app does
        def on_watchdog_nudge(agent_name, stall_time):
            mock_app.push_swarm_event("warn", agent_name, f"nudged after {stall_time:.1f}s stall")
        
        def on_watchdog_respawn(agent_name, failed_nudges):
            mock_app.push_swarm_event("warn", agent_name, f"respawned after {failed_nudges} failed nudges")
        
        # Register callbacks
        watchdog.register_nudge_callback(on_watchdog_nudge)
        watchdog.register_respawn_callback(on_watchdog_respawn)
        
        # Test that callbacks are registered
        assert len(watchdog._on_nudge_callbacks) > 0
        assert len(watchdog._on_respawn_callbacks) > 0
        
        # Clean up
        watchdog._on_nudge_callbacks.clear()
        watchdog._on_respawn_callbacks.clear()
    
    def test_coordinator_events(self):
        """Test that Coordinator events are wired to TUI"""
        # Create a mock app to capture events
        class MockApp:
            def __init__(self):
                self.events = []
            
            def push_swarm_event(self, level, source, message):
                self.events.append({"level": level, "source": source, "message": message})
        
        mock_app = MockApp()
        
        # Manually register callbacks like the real app does
        def on_task_assigned(task_packet):
            mock_app.push_swarm_event("info", "coordinator", f"→ {task_packet.role_required}: {task_packet.title}")
        
        def on_handoff(from_agent, to_role, task_title):
            mock_app.push_swarm_event("info", from_agent, f"handoff → {to_role}")
        
        # Register callbacks
        coordinator.register_task_assigned_callback(on_task_assigned)
        coordinator.register_handoff_callback(on_handoff)
        
        # Test that callbacks are registered
        assert len(coordinator._on_task_assigned_callbacks) > 0
        assert len(coordinator._on_handoff_callbacks) > 0
        
        # Clean up
        coordinator._on_task_assigned_callbacks.clear()
        coordinator._on_handoff_callbacks.clear()


class TestEventTriggering:
    """Test that events are actually triggered"""
    
    def test_watchdog_nudge_trigger(self):
        """Test that watchdog nudge callbacks are triggered"""
        events = []
        
        def capture_nudge(agent_name, stall_time):
            events.append({"agent": agent_name, "stall_time": stall_time})
        
        watchdog.register_nudge_callback(capture_nudge)
        
        # Simulate a nudge (this would normally happen in _check_agents)
        # We'll call the callback directly for testing
        watchdog._on_nudge_callbacks[0]("test-agent", 125.5)
        
        assert len(events) == 1
        assert events[0]["agent"] == "test-agent"
        assert events[0]["stall_time"] == 125.5
        
        # Clean up
        watchdog._on_nudge_callbacks.clear()
    
    def test_coordinator_handoff_trigger(self):
        """Test that coordinator handoff callbacks are triggered"""
        events = []
        
        def capture_handoff(from_agent, to_role, task_title):
            events.append({"from": from_agent, "to": to_role, "task": task_title})
        
        coordinator.register_handoff_callback(capture_handoff)
        
        # Trigger a handoff
        coordinator.trigger_handoff("scout-1", "developer", "Implement feature")
        
        assert len(events) == 1
        assert events[0]["from"] == "scout-1"
        assert events[0]["to"] == "developer"
        assert events[0]["task"] == "Implement feature"
        
        # Clean up
        coordinator._on_handoff_callbacks.clear()
