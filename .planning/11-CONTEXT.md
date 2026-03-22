# Phase 11 Context: Goal Decomposition v2

## Overview
Phase 11 upgrades the `Overseer` and `Coordinator` to support complex, non-linear task graphs. Instead of simple lists, Swarm will manage a Directed Acyclic Graph (DAG) of tasks with conditional execution.

## Implementation Decisions

### Task Graph Model
- Tasks will include a `depends_on: List[str]` field (already present in `TaskPacket` but needs robust enforcement).
- Introduce `condition: Optional[str]` for conditional branching (e.g., "only run Task B if Task A returns status: error").

### Execution Engine
- The `Coordinator` will manage the task queue using a dependency resolver.
- Parallel workstreams: Tasks with no unmet dependencies will be spawned immediately up to the fleet limit.
- Blocking: Tasks with unmet dependencies stay in `queued` state.

### TUI Visualization
- Create a `TaskGraphPanel` that shows the relationship between tasks.
- Use color-coding for status: Gray (Queued), Green (Running), Blue (Done), Red (Error).

## Gray Areas
- How to handle loops in the task graph? *Decision: Forbidden for now; keep it as a DAG to avoid infinite cycles. If retry is needed, use the Reflection/Retry mechanism.*
- Re-planning: Should the Overseer re-plan the entire graph if a task fails? *Decision: Yes, support "Dynamic Re-planning" as a trigger.*
