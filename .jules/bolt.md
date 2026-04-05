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

## 2025-04-05 - Task Graph Scan Optimization
**Learning:** Found that when processing thousands of tasks, the `_scan_for_overlaps` function in `src/orchestrator/coordinator.py` suffered from severe latency (~1.44s for 4000 tasks). This was caused by an $O(N \times F \times K)$ issue where `set(other_task.files_in_scope)` was repeatedly instantiated inside a nested loop for every shared file.
**Action:** Optimized the loop by computing `set(task.files_in_scope)` once per task and caching it alongside the task packet as a tuple in the local index (`file_to_tasks`). This reduced scan time for 4000 tasks down to ~0.78s (approx. 45% reduction). Avoid redundant object instantiations within tight loops, especially when checking set intersections.
