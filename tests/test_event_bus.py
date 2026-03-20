"""
Test suite for the event bus system.
"""

import asyncio
import time
import pytest
from unittest.mock import MagicMock

from src.messaging.event_bus import EventBus, Event
from src.messaging.db import SwarmDB


@pytest.fixture
async def event_bus():
    """Create a test event bus with clean database."""
    # Use a test database
    db = EventBus(".polyglot/test_event_bus.db")
    # Ensure database is connected
    await db.db.connect()
    await db.clear_events()
    return db


class TestEventBusEmit:
    
    async def test_emit_basic_event(self, event_bus):
        """Test emitting a basic event."""
        await event_bus.emit("test", "source", {"key": "value"})
        
        count = await event_bus.get_event_count()
        assert count == 1
    
    async def test_emit_with_session_and_agent(self, event_bus):
        """Test emitting event with session and agent info."""
        await event_bus.emit(
            "spawn", 
            "agent-manager", 
            {"agent": "test-agent"},
            session_id="test-session-123",
            agent_name="test-agent"
        )
        
        events = await event_bus.replay()
        assert len(events) == 1
        assert events[0].session_id == "test-session-123"
        assert events[0].agent_name == "test-agent"
    
    async def test_emit_multiple_events(self, event_bus):
        """Test emitting multiple events."""
        for i in range(5):
            await event_bus.emit(f"event-{i}", "source", {"index": i})
        
        count = await event_bus.get_event_count()
        assert count == 5


class TestEventBusSubscribe:
    
    async def test_subscribe_and_receive(self, event_bus):
        """Test subscribing to events and receiving them."""
        received_events = []
        
        def callback(event):
            received_events.append(event)
        
        event_bus.subscribe("test", callback)
        
        # Emit an event
        await event_bus.emit("test", "source", {"data": "test"})
        
        # Give a moment for async processing
        await asyncio.sleep(0.1)
        
        assert len(received_events) == 1
        assert received_events[0].event_type == "test"
    
    async def test_subscribe_wildcard(self, event_bus):
        """Test subscribing to all events with wildcard."""
        received_events = []
        
        def callback(event):
            received_events.append(event)
        
        event_bus.subscribe("*", callback)
        
        # Emit different event types
        await event_bus.emit("type1", "source1", {})
        await event_bus.emit("type2", "source2", {})
        
        await asyncio.sleep(0.1)
        
        assert len(received_events) == 2
    
    async def test_multiple_subscribers(self, event_bus):
        """Test multiple subscribers for same event type."""
        subscriber1_events = []
        subscriber2_events = []
        
        def callback1(event):
            subscriber1_events.append(event)
        
        def callback2(event):
            subscriber2_events.append(event)
        
        event_bus.subscribe("test", callback1)
        event_bus.subscribe("test", callback2)
        
        await event_bus.emit("test", "source", {})
        await asyncio.sleep(0.1)
        
        assert len(subscriber1_events) == 1
        assert len(subscriber2_events) == 1


class TestEventBusReplay:
    
    async def test_replay_all_events(self, event_bus):
        """Test replaying all events."""
        # Emit some events
        for i in range(3):
            await event_bus.emit(f"type-{i}", f"source-{i}", {"index": i})
            await asyncio.sleep(0.01)  # Small delay for timestamp differences
        
        events = await event_bus.replay()
        assert len(events) == 3
        
        # Check order by timestamp
        timestamps = [e.timestamp for e in events]
        assert timestamps == sorted(timestamps)
    
    async def test_replay_since_timestamp(self, event_bus):
        """Test replaying events since specific timestamp."""
        # Emit events with delays
        start_time = time.time()
        await event_bus.emit("old", "source", {})
        await asyncio.sleep(0.05)
        
        midpoint = time.time()
        await event_bus.emit("new", "source", {})
        
        # Replay from midpoint
        recent_events = await event_bus.replay(since_timestamp=midpoint)
        assert len(recent_events) == 1
        assert recent_events[0].event_type == "new"
    
    async def test_replay_filter_by_type(self, event_bus):
        """Test replaying events filtered by type."""
        # Emit different types
        await event_bus.emit("keep", "source", {})
        await event_bus.emit("filter", "source", {})
        await event_bus.emit("keep", "source", {})
        
        # Replay only 'keep' events
        events = await event_bus.replay(event_types=["keep"])
        assert len(events) == 2
        assert all(e.event_type == "keep" for e in events)
    
    async def test_replay_empty(self, event_bus):
        """Test replay when no events match criteria."""
        events = await event_bus.replay(since_timestamp=time.time() + 1000)
        assert len(events) == 0


class TestEventBusPersistence:
    
    async def test_event_persistence(self, event_bus):
        """Test that events are persisted to database."""
        test_data = {"key": "value", "nested": {"data": 123}}
        await event_bus.emit("test", "source", test_data)
        
        # Read directly from database
        rows = await event_bus.db.fetch_all("SELECT * FROM events")
        assert len(rows) == 1
        
        # Verify data was stored correctly
        stored_data = json.loads(rows[0][5])  # data column
        assert stored_data == test_data
    
    async def test_persistence_across_restart(self, event_bus):
        """Test that events persist across event bus restarts."""
        # Emit some events
        await event_bus.emit("event1", "source", {"data": 1})
        await event_bus.emit("event2", "source", {"data": 2})
        
        # Create new event bus instance (simulating restart)
        new_bus = EventBus(".polyglot/test_event_bus.db")
        
        # Should still have the events
        events = await new_bus.replay()
        assert len(events) == 2
        
        # Clean up
        await new_bus.clear_events()
    
    async def test_clear_events(self, event_bus):
        """Test clearing all events."""
        # Add some events
        for i in range(5):
            await event_bus.emit(f"event-{i}", "source", {})
        
        # Clear them
        await event_bus.clear_events()
        
        # Verify they're gone
        count = await event_bus.get_event_count()
        assert count == 0


class TestEventBusIntegration:
    
    async def test_integration_with_coordinator(self, event_bus):
        """Test event bus integration with coordinator."""
        from src.orchestrator.coordinator import Coordinator
        
        coordinator = Coordinator()
        
        # Subscribe to coordinator events
        received_events = []
        
        async def async_callback(event):
            received_events.append(event)
        
        event_bus.subscribe("info", async_callback)
        
        # Set coordinator to use event bus
        def event_callback(type, source, message):
            asyncio.create_task(event_bus.emit(type, source, {"message": message}))
        coordinator._push_event_callback = event_callback
        
        # Trigger an event
        await coordinator.decompose_task("test task")
        
        # Give time for async processing
        await asyncio.sleep(0.2)
        
        # Should have received events
        assert len(received_events) > 0
    
    async def test_tui_reconnect_recovery(self, event_bus):
        """Test TUI reconnect recovery using replay."""
        # Simulate TUI being connected and receiving events
        last_timestamp = time.time()
        
        # Emit events while TUI is connected
        await event_bus.emit("spawn", "agent-manager", {"agent": "agent1"})
        await event_bus.emit("status", "agent1", {"status": "running"})
        
        # TUI disconnects and reconnects later
        await asyncio.sleep(0.1)
        disconnect_time = time.time()
        
        # More events happen while TUI is disconnected
        await event_bus.emit("spawn", "agent-manager", {"agent": "agent2"})
        await event_bus.emit("status", "agent2", {"status": "running"})
        
        # TUI reconnects and requests missed events
        missed_events = await event_bus.replay(since_timestamp=disconnect_time)
        
        # Should get the events that happened during disconnection
        assert len(missed_events) == 2
        assert missed_events[0].event_type == "spawn"
        assert missed_events[1].event_type == "status"


class TestEventBusPerformance:
    
    async def test_bulk_events(self, event_bus):
        """Test handling bulk events efficiently."""
        start_time = time.time()
        
        # Emit 100 events
        for i in range(100):
            await event_bus.emit(f"event-{i}", "source", {"index": i})
        
        end_time = time.time()
        
        # Should complete in reasonable time
        assert end_time - start_time < 1.0  # Less than 1 second for 100 events
        
        # Verify all persisted
        count = await event_bus.get_event_count()
        assert count == 100
    
    async def test_many_subscribers(self, event_bus):
        """Test performance with many subscribers."""
        # Create 50 subscribers
        callbacks = []
        for i in range(50):
            events = []
            def callback(event):
                events.append(event)
            callbacks.append(callback)
            event_bus.subscribe("test", callback)
        
        start_time = time.time()
        
        # Emit an event
        await event_bus.emit("test", "source", {})
        
        end_time = time.time()
        
        # Should handle many subscribers efficiently
        assert end_time - start_time < 0.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
