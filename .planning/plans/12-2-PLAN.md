# Plan 12-2: Arbiter Role & Integration

## Objective
Define and deploy the `Arbiter` role to resolve detected conflicts.

## Tasks
1. **Arbiter Definition**: Create `src/agents/definitions/arbiter.md` and `src/roles/contracts/arbiter.yaml`.
2. **Resolution Logic**: Implement `resolve_conflict(task_a, task_b)` in `Coordinator` which spawns an Arbiter agent.
3. **Outcome Application**: Implement logic to apply the Arbiter's verdict (sequentialize, cancel, or merge tasks).
4. **TUI Alert**: Add a visible conflict warning in the `TaskGraphPanel` or `EventLog`.

## Verification
- [ ] Arbiter role is correctly registered.
- [ ] A detected conflict triggers an Arbiter spawn and successful resolution in a test scenario.
