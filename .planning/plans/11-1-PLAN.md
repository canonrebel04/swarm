# Plan 11-1: Dependency Resolution Logic

## Objective
Enable the `Coordinator` to resolve and enforce task dependencies using a DAG model.

## Tasks
1. **Task Metadata**: Ensure `TaskPacket` correctly tracks `depends_on` (task titles or IDs).
2. **Dependency Resolver**: Implement `_get_ready_tasks()` in `Coordinator` to identify tasks with all dependencies met.
3. **Execution State**: Add `status: str` to `TaskPacket` (pending, blocked, ready, active, completed, failed).
4. **Graph Validation**: Add a check to prevent circular dependencies during decomposition.

## Verification
- [ ] Unit test: Given a graph of 5 tasks, correctly identifies which can start first.
- [ ] Circular dependency detection prevents invalid graphs.
