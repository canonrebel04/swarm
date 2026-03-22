# Plan 06-3: Qodo Adapter & Registry Update

## Objective
Implement `QodoRuntime` in `src/runtimes/qodo.py` and register all Phase 6 adapters.

## Tasks
1. **Adapter Skeleton**: Implement `QodoRuntime` class inheriting from `AgentRuntime`.
2. **Spawn Logic**: Use `qodo --ci -y "..."` for headless execution.
3. **Register Adapters**: Update `src/runtimes/registry.py` to import and register `GooseRuntime`, `ClineRuntime`, and `QodoRuntime`.
4. **Final Verification**: Ensure all new runtimes appear in `swarm runtimes` list.

## Verification
- [ ] Runtimes correctly registered.
- [ ] Listed in TUI model selector.
