# Plan 04-3: Supervisor Intervention Workflow

## Objective
Standardize and expose agent intervention actions (nudge, kill, pause) and integrate with safety monitoring.

## Tasks
1. **Standardize Runtime Kill**: Ensure all `AgentRuntime.kill()` implementations are robust and cleanup resources.
2. **Implement Nudge**: Finalize `AgentRuntime.send_message()` across all runtimes to support follow-up prompts.
3. **Link AntiDrift to Supervisor**: Update `AntiDriftMonitor` to emit events that the `Supervisor` (or Overseer) can act upon.
4. **TUI Actions**: Ensure the `AgentFleet` panel correctly triggers these intervention actions via the `EventBus`.

## Verification
- [ ] User can successfully nudge a stalled agent from the TUI.
- [ ] Role violation detected by `AntiDriftMonitor` triggers a visible warning in the event log.
- [ ] `AgentRuntime.kill()` successfully terminates the process and releases the worktree.
