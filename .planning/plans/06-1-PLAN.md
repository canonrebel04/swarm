# Plan 06-1: Goose Adapter Implementation

## Objective
Implement `GooseRuntime` in `src/runtimes/goose.py`.

## Tasks
1. **Adapter Skeleton**: Implement `GooseRuntime` class inheriting from `AgentRuntime`.
2. **Spawn Logic**: Use `goose run -t "..." --instructions <path>` for headless execution.
3. **Output Capture**: Capture and yield results from stdout.
4. **Error Handling**: Map exit codes to agent states.

## Verification
- [ ] Manual test with `goose` binary.
- [ ] Unit test `tests/test_goose_runtime.py` (mocked).
