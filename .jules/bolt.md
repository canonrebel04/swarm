## 2024-03-30 - Bolt initialized
## 2024-03-30 - Database Index Optimization
**Learning:** Found that the messaging and state management database uses SQLite but lacks indexes on commonly queried columns. For example, `messages` is queried by `session_id` and sorted by `timestamp`, and `events` is sorted by `timestamp`. Without indexes, these queries will require full table scans, which can become a bottleneck as the SQLite database grows.
**Action:** Add database indexes to frequently queried and sorted columns (like `session_id` and `timestamp` in `messages` and `events`) to improve backend query performance.

## $(date +%Y-%m-%d) - asyncio.run_coroutine_threadsafe inside an event loop
**Learning:** In `src/orchestrator/coordinator.py`, `_scan_for_overlaps` used `asyncio.run_coroutine_threadsafe(swarm_db.get_locked_resources(), asyncio.get_event_loop())` synchronously, expecting it to return a list. However, because it ran inside an async context (`process_task_queue`), it returned a `Future` instead of an evaluated value, causing a `TypeError` when `intersection()` tried to iterate over it. It also needlessly blocked the event loop.
**Action:** Changed `_scan_for_overlaps` to be `async def`, `await` it in the caller, and directly `await swarm_db.get_locked_resources()`. Avoid using `run_coroutine_threadsafe` when you are already in an async event loop unless interacting with threads.
