"""
SQLite database setup for messaging and state management.
"""

import aiosqlite
import asyncio
from typing import Optional
import os


class SwarmDB:
    """SQLite database for storing swarm messages and state."""

    def __init__(self, db_path: str = ".swarm/messages.db"):
        self.db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

    async def connect(self) -> None:
        """Connect to the database."""
        self._conn = await aiosqlite.connect(self.db_path)
        await self._initialize_schema()

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _initialize_schema(self) -> None:
        """Initialize database schema."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                message_type TEXT NOT NULL
            )
        """)

        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                agent_name TEXT NOT NULL,
                role TEXT NOT NULL,
                runtime TEXT NOT NULL,
                state TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                session_id TEXT,
                agent_name TEXT,
                data TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await self._conn.commit()

    async def add_message(
        self, 
        session_id: str, 
        sender: str, 
        content: str, 
        message_type: str = "text"
    ) -> None:
        """Add a message to the database."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        await self._conn.execute(
            """
            INSERT INTO messages (session_id, sender, content, message_type)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, sender, content, message_type)
        )
        await self._conn.commit()

    async def get_messages(self, session_id: str, limit: int = 100) -> list[tuple]:
        """Get messages for a session."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        cursor = await self._conn.execute(
            """
            SELECT sender, content, timestamp, message_type
            FROM messages
            WHERE session_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (session_id, limit)
        )
        
        return await cursor.fetchall()

    async def create_agent_session(
        self, 
        session_id: str, 
        agent_name: str, 
        role: str, 
        runtime: str, 
        state: str = "queued"
    ) -> None:
        """Create a new agent session record."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        await self._conn.execute(
            """
            INSERT INTO agent_sessions 
            (session_id, agent_name, role, runtime, state)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, agent_name, role, runtime, state)
        )
        await self._conn.commit()

    async def update_agent_state(self, session_id: str, state: str) -> None:
        """Update the state of an agent session."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        await self._conn.execute(
            """
            UPDATE agent_sessions
            SET state = ?, updated_at = CURRENT_TIMESTAMP
            WHERE session_id = ?
            """,
            (state, session_id)
        )
        await self._conn.commit()

    async def get_agent_sessions(self) -> list[tuple]:
        """Get all active agent sessions."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        cursor = await self._conn.execute(
            """
            SELECT session_id, agent_name, role, runtime, state
            FROM agent_sessions
            ORDER BY updated_at DESC
            """
        )
        
        return await cursor.fetchall()

    async def add_event(
        self, 
        event_type: str, 
        session_id: Optional[str] = None, 
        agent_name: Optional[str] = None, 
        data: Optional[str] = None
    ) -> None:
        """Add an event to the event log."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        await self._conn.execute(
            """
            INSERT INTO events (event_type, session_id, agent_name, data)
            VALUES (?, ?, ?, ?)
            """,
            (event_type, session_id, agent_name, data)
        )
        await self._conn.commit()

    async def get_recent_events(self, limit: int = 50) -> list[tuple]:
        """Get recent events."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        cursor = await self._conn.execute(
            """
            SELECT event_type, session_id, agent_name, data, timestamp
            FROM events
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (limit,)
        )
        
        return await cursor.fetchall()

    async def clear_events(self) -> None:
        """Clear all events from the events table."""
        if not self._conn:
            raise RuntimeError("Database not connected")
        
        await self._conn.execute("DELETE FROM events")
        await self._conn.commit()


# Global database instance
db = SwarmDB()


async def init_db():
    """Initialize the database connection."""
    await db.connect()


async def close_db():
    """Close the database connection."""
    await db.close()