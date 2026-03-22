# Plan 06-2: Cline Adapter Implementation

## Objective
Implement `ClineRuntime` in `src/runtimes/cline.py`.

## Tasks
1. **Adapter Skeleton**: Implement `ClineRuntime` class inheriting from `AgentRuntime`.
2. **Spawn Logic**: Use `cline -y "..."` for headless execution.
3. **Output Stream**: Capture output lines and yield to event bus.
4. **Isolation**: Ensure `cwd` is set to worktree path.

## Verification
- [ ] Manual test with `cline` binary.
- [ ] Unit test `tests/test_cline_runtime.py` (mocked).
