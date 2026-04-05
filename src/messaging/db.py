"""
SQLite database setup for messaging and state management.
"""

import asyncio
import os
from typing import Optional

import aiosqlite

# Canonical database path — all modules should use this
DB_DIR = os.path.join(".swarm", "data")
DB_PATH = os.path.join(DB_DIR, "swarm.db")


class SwarmDB:
    """SQLite database for storing swarm messages and state."""

    def __init__(self, db_path: str = DB_PATH):
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

        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                message_type TEXT NOT NULL
            )
        """
        )

        await self._conn.execute(
            """
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
        """
        )

        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                session_id TEXT,
                agent_name TEXT,
                data TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS experience_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                task_title TEXT NOT NULL,
                status TEXT NOT NULL,
                critique TEXT,
                lessons_learned TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS swarm_instances (
                swarm_id TEXT PRIMARY KEY,
                last_heartbeat DATETIME DEFAULT CURRENT_TIMESTAMP,
                capabilities TEXT,
                status TEXT
            )
        """
        )

        await self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS resource_locks (
                resource_path TEXT PRIMARY KEY,
                swarm_id TEXT NOT NULL,
                expires_at DATETIME NOT NULL
            )
        """
        )

        # ⚡ Bolt: Composite index to optimize `get_messages` query.
        # Allows SQLite to scan the index and return rows in correct order,
        # avoiding an O(N log N) filesort for message history queries.
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_session_id_timestamp ON messages (session_id, timestamp DESC)"
        )
        await self._conn.execute(
            # Composite index on session_id and timestamp DESC to optimize get_messages query
            "CREATE INDEX IF NOT EXISTS idx_messages_session_timestamp ON messages (session_id, timestamp DESC)"
        )
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events (timestamp DESC)"
        )
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_experience_logs_role ON experience_logs (role)"
        )
        await self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_resource_locks_expires_at ON resource_locks (expires_at)"
        )

        await self._conn.commit()

    async def add_message(
        self, session_id: str, sender: str, content: str, message_type: str = "text"
    ) -> None:
        """Add a message to the database."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        await self._conn.execute(
            """
            INSERT INTO messages (session_id, sender, content, message_type)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, sender, content, message_type),
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
            (session_id, limit),
        )

        return await cursor.fetchall()

    async def get_event_count(self) -> int:
        """Get total number of events."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        cursor = await self._conn.execute("SELECT COUNT(*) FROM events")
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def create_agent_session(
        self,
        session_id: str,
        agent_name: str,
        role: str,
        runtime: str,
        state: str = "queued",
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
            (session_id, agent_name, role, runtime, state),
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
            (state, session_id),
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
        data: Optional[str] = None,
    ) -> None:
        """Add an event to the event log."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        await self._conn.execute(
            """
            INSERT INTO events (event_type, session_id, agent_name, data)
            VALUES (?, ?, ?, ?)
            """,
            (event_type, session_id, agent_name, data),
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
            (limit,),
        )

        return await cursor.fetchall()

    async def register_swarm_instance(self, swarm_id: str, capabilities: str) -> None:
        """Register or update a swarm instance heartbeat."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        await self._conn.execute(
            """
            INSERT INTO swarm_instances (swarm_id, capabilities, status, last_heartbeat)
            VALUES (?, ?, 'active', CURRENT_TIMESTAMP)
            ON CONFLICT(swarm_id) DO UPDATE SET
                last_heartbeat = CURRENT_TIMESTAMP,
                capabilities = excluded.capabilities,
                status = 'active'
            """,
            (swarm_id, capabilities),
        )
        await self._conn.commit()

    async def get_active_swarms(self, timeout_seconds: int = 60) -> list[tuple]:
        """Get list of swarms that have sent a heartbeat recently."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        cursor = await self._conn.execute(
            f"""
            SELECT swarm_id, capabilities, last_heartbeat
            FROM swarm_instances
            WHERE last_heartbeat > datetime('now', '-{timeout_seconds} seconds')
            """
        )
        return await cursor.fetchall()

    async def acquire_lock(
        self, resource_path: str, swarm_id: str, timeout_seconds: int = 300
    ) -> bool:
        """Attempt to acquire a lock on a resource for a specific swarm."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        # First clear expired locks
        await self._conn.execute(
            "DELETE FROM resource_locks WHERE expires_at < CURRENT_TIMESTAMP"
        )

        try:
            await self._conn.execute(
                """
                INSERT INTO resource_locks (resource_path, swarm_id, expires_at)
                VALUES (?, ?, datetime('now', '+' || ? || ' seconds'))
                """,
                (resource_path, swarm_id, timeout_seconds),
            )
            await self._conn.commit()
            return True
        except Exception:  # UNIQUE constraint failed
            # If the lock is already held by THIS swarm, we can extend it
            cursor = await self._conn.execute(
                "SELECT swarm_id FROM resource_locks WHERE resource_path = ?",
                (resource_path,),
            )
            row = await cursor.fetchone()
            if row and row[0] == swarm_id:
                await self._conn.execute(
                    """
                    UPDATE resource_locks 
                    SET expires_at = datetime('now', '+' || ? || ' seconds')
                    WHERE resource_path = ? AND swarm_id = ?
                    """,
                    (timeout_seconds, resource_path, swarm_id),
                )
                await self._conn.commit()
                return True
            return False

    async def release_lock(self, resource_path: str, swarm_id: str) -> None:
        """Release a lock held by a swarm."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        await self._conn.execute(
            "DELETE FROM resource_locks WHERE resource_path = ? AND swarm_id = ?",
            (resource_path, swarm_id),
        )
        await self._conn.commit()

    async def get_locked_resources(self) -> list[str]:
        """Get a list of all currently locked resources."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        # ⚡ Bolt Optimization: Filter out expired locks in the SELECT query
        # instead of performing a DELETE write transaction on every read.
        # This avoids taking an unnecessary SQLite write lock during read-heavy polling
        # (e.g., coordinator scanning for overlaps).
        cursor = await self._conn.execute(
            "SELECT resource_path FROM resource_locks WHERE expires_at >= CURRENT_TIMESTAMP"
        )
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def add_experience_log(
        self,
        role: str,
        task_title: str,
        status: str,
        critique: Optional[str] = None,
        lessons_learned: Optional[str] = None,
    ) -> None:
        """Add a new experience log entry."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        await self._conn.execute(
            """
            INSERT INTO experience_logs (role, task_title, status, critique, lessons_learned)
            VALUES (?, ?, ?, ?, ?)
            """,
            (role, task_title, status, critique, lessons_learned),
        )
        await self._conn.commit()

    async def get_lessons_for_role(self, role: str, limit: int = 3) -> list[str]:
        """Get synthesized lessons for a specific role."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        cursor = await self._conn.execute(
            """
            SELECT lessons_learned
            FROM experience_logs
            WHERE role = ? AND lessons_learned IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (role, limit),
        )

        rows = await cursor.fetchall()
        return [row[0] for row in rows]

    async def get_recent_critiques(
        self, role: Optional[str] = None, limit: int = 10
    ) -> list[tuple]:
        """Get recent critiques for reflection."""
        if not self._conn:
            raise RuntimeError("Database not connected")

        query = "SELECT role, task_title, status, critique FROM experience_logs WHERE lessons_learned IS NULL"
        params: list[str | int] = []
        if role:
            query += " AND role = ?"
            params.append(role)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = await self._conn.execute(query, tuple(params))
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
