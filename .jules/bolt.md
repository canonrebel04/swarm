## 2025-04-03 - EventBus Replay Filtering Optimization
**Learning:** Found that filtering large event streams at the application level by querying all records from SQLite and using Python JSON parsing + dict iteration leads to severe overhead and high I/O.
**Action:** Always push event and type filtering down into the database layer via parameterized SQL queries. Even if SQLite stores timestamps as text making float comparison difficult in pure SQL, filtering by `event_type` (`IN (?, ?)`) directly in SQL removes massive amounts of JSON parsing overhead.
## 2024-03-30 - Bolt initialized
## 2024-03-30 - Database Index Optimization
**Learning:** Found that the messaging and state management database uses SQLite but lacks indexes on commonly queried columns. For example, `messages` is queried by `session_id` and sorted by `timestamp`, and `events` is sorted by `timestamp`. Without indexes, these queries will require full table scans, which can become a bottleneck as the SQLite database grows.
**Action:** Add database indexes to frequently queried and sorted columns (like `session_id` and `timestamp` in `messages` and `events`) to improve backend query performance.

## $(date +%Y-%m-%d) - asyncio.run_coroutine_threadsafe inside an event loop
**Learning:** In `src/orchestrator/coordinator.py`, `_scan_for_overlaps` used `asyncio.run_coroutine_threadsafe(swarm_db.get_locked_resources(), asyncio.get_event_loop())` synchronously, expecting it to return a list. However, because it ran inside an async context (`process_task_queue`), it returned a `Future` instead of an evaluated value, causing a `TypeError` when `intersection()` tried to iterate over it. It also needlessly blocked the event loop.
**Action:** Changed `_scan_for_overlaps` to be `async def`, `await` it in the caller, and directly `await swarm_db.get_locked_resources()`. Avoid using `run_coroutine_threadsafe` when you are already in an async event loop unless interacting with threads.

## 2025-03-01 - Optimizing Event Bus Row Counting
**Learning:** In the event bus system (`src/messaging/event_bus.py`), fetching large datasets entirely into memory to count their size (using `len(await self.db.get_recent_events(limit=999999))`) creates severe latency and memory spikes, slowing down system-wide monitoring.
**Action:** Always prefer native database aggregations (like `SELECT COUNT(*) FROM events`) over application-side counting for large tables. I refactored `SwarmDB` to include an optimized `get_event_count` query.
## 2024-04-04 - SQLite JSON filtering overhead
**Learning:** `EventBus.replay` was fetching `limit=1000` events and parsing their JSON payloads in Python just to discard most of them based on `event_type` and `timestamp`. This caused a major CPU bottleneck and high memory usage.
**Action:** Always push filtering down to the database level (e.g. `WHERE event_type IN (...) AND timestamp > ?`) using SQL indexes instead of doing in-memory JSON parsing and list filtering in Python.

## 2024-04-08 - Vanilla JS Proxy Thrashing
**Learning:** Using a naive Javascript `Proxy` setter to directly trigger synchronous UI renders causes significant main thread blocking and layout thrashing, especially when bursty events (like rapid WebSocket signals) occur.
**Action:** Always decouple reactive state updates from synchronous DOM rendering by batching UI changes with `requestAnimationFrame` when using raw Proxies for state management in vanilla JS apps. Furthermore, API requests triggered by rapid state streams should be debounced.
