"""
Event bus system for centralized event management and persistence.

This module provides a unified event bus that:
1. Persists events to SQLite database
2. Fires registered callbacks
3. Supports event replay for TUI recovery
4. Replaces direct _event_callback() calls
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from .db import DB_PATH, SwarmDB


@dataclass
class Event:
    """Represents a system event."""

    event_id: str
    event_type: str
    source: str
    data: dict
    timestamp: float
    session_id: Optional[str] = None
    agent_name: Optional[str] = None
    target_swarm: Optional[str] = None


class EventBus:
    """Centralized event bus with persistence and callback support."""

    def __init__(self, db_path: str = DB_PATH):
        self.db = SwarmDB(db_path)
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = asyncio.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database tables for events."""
        # The events table should already exist from SwarmDB initialization
        # If not, it will be created when we first use it
        pass

    async def emit(
        self,
        event_type: str,
        source: str,
        data: dict,
        session_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        target_swarm: Optional[str] = None,
    ) -> None:
        """
        Emit an event that will be persisted and sent to subscribers.

        Args:
            event_type: Type of event (e.g., 'spawn', 'error', 'warning')
            source: Source of the event (e.g., 'coordinator', 'agent-manager')
            data: Event data payload
            session_id: Optional session ID for correlation
            agent_name: Optional agent name for correlation
            target_swarm: Optional target swarm ID for cross-swarm events
        """
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            source=source,
            data=data,
            timestamp=time.time(),
            session_id=session_id,
            agent_name=agent_name,
            target_swarm=target_swarm,
        )

        # Persist event to database
        await self._persist_event(event)

        # Notify subscribers
        await self._notify_subscribers(event)

    async def _persist_event(self, event: Event) -> None:
        """Persist event to SQLite database using existing SwarmDB method."""
        # Convert our event data to JSON string for the existing schema
        data_json = json.dumps(
            {
                **event.data,
                "_event_id": event.event_id,
                "_source": event.source,
                "_timestamp": event.timestamp,
                "_target_swarm": event.target_swarm,
            }
        )

        await self.db.add_event(
            event_type=event.event_type,
            session_id=event.session_id,
            agent_name=event.agent_name,
            data=data_json,
        )

    async def _notify_subscribers(self, event: Event) -> None:
        """Notify all subscribers for this event type."""
        async with self._lock:
            # Notify type-specific subscribers
            for callback in self._subscribers.get(event.event_type, []):
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    print(f"Error in event callback: {e}")

            # Notify wildcard subscribers
            for callback in self._subscribers.get("*", []):
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(event)
                    else:
                        callback(event)
                except Exception as e:
                    print(f"Error in event callback: {e}")

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """
        Subscribe to events of a specific type.

        Args:
            event_type: Event type to subscribe to, or "*" for all events
            callback: Callback function to receive events
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    async def replay(
        self,
        since_timestamp: Optional[float] = None,
        event_types: Optional[List[str]] = None,
    ) -> List[Event]:
        """
        Replay events from a specific timestamp.

        Args:
            since_timestamp: Only return events after this timestamp
            event_types: Only return events of these types

        Returns:
            List of Event objects
        """
        # ⚡ Bolt Optimization: Push filtering down to the DB to avoid
        # fetching and JSON-parsing thousands of events unnecessarily.
        all_events = await self.db.get_recent_events(
            limit=1000,
            since_timestamp=since_timestamp,
            event_types=event_types,
        )

        events = []
        for row in all_events:
            try:
                # Parse the stored JSON data
                event_data = json.loads(row[3])  # data column

                # Reconstruct the event
                event = Event(
                    event_id=event_data.get("_event_id", str(uuid.uuid4())),
                    event_type=row[0],  # event_type column
                    source=event_data.get("_source", "unknown"),
                    session_id=row[1],  # session_id column
                    agent_name=row[2],  # agent_name column
                    data={k: v for k, v in event_data.items() if not k.startswith("_")},
                    timestamp=event_data.get("_timestamp", time.time()),
                )

                events.append(event)

            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error parsing event data: {e}")
                continue

        # Sort by timestamp
        events.sort(key=lambda e: e.timestamp)
        return events

    async def get_events_since(self, timestamp: float, limit: int = 100) -> List[Event]:
        """Get recent events since a timestamp (for TUI updates)."""
        return await self.replay(since_timestamp=timestamp)

    async def clear_events(self) -> None:
        """Clear all events (for testing)."""
        # Use the SwarmDB method we just added
        await self.db.clear_events()

    async def get_event_count(self) -> int:
        """Get total number of events."""
        # ⚡ Bolt Optimization: Use optimized database query instead of fetching all records
        return await self.db.get_event_count()


# Global event bus instance
event_bus = EventBus()
