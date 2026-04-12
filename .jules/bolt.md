## 2026-04-10 - Recursive Depth-First Search in Coordinators
**Learning:** Python's recursion limit (~1000 by default) makes recursive DFS a critical point of failure for large task dependency graphs in `src/orchestrator/coordinator.py`. While elegant, a deep chain of `depends_on` relationships will trigger a `RecursionError` and crash the orchestrator process completely.
**Action:** Always prefer an explicit stack-based iterative approach when traversing the Swarm's task graph. This eliminates function overhead and scales seamlessly to tens of thousands of tasks without risking hard crashes.
