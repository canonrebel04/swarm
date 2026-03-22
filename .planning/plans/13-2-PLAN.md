# Plan 13-2: Hierarchical Delegation

## Objective
Support the "Swarm of Swarms" model by allowing a Swarm to act as an agent.

## Tasks
1. **Delegation Logic**: Update `Coordinator.assign_task` to handle `target_swarm` assignments.
2. **Remote Task Wrapper**: Create a specialized "RemoteSwarm" adapter that maps a local task to an external Swarm objective.
3. **State Sync**: Implement logic to forward sub-swarm progress back to the parent Swarm's task graph.
4. **Handoff Proxy**: Ensure `Reviewer` and `Merger` results can traverse Swarm boundaries.

## Verification
- [ ] Parent Swarm correctly spawns a task that is executed and completed by a Child Swarm.
- [ ] Visual task graph in Parent Swarm shows "External Swarm" as the active worker.
