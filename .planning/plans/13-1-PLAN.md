# Plan 13-1: Inter-Swarm Communication Protocol

## Objective
Enable Swarm instances to discover and exchange events with each other.

## Tasks
1. **Swarm Identity**: Add `swarm_id` and `capabilities` to the global state.
2. **Discovery Service**: Implement a simple registry in `SwarmDB` to track active Swarm instances.
3. **Cross-Swarm Events**: Extend `EventBus.emit()` to support a `target_swarm` parameter.
4. **Synchronization**: Implement a background loop to poll or listen for events from other Swarms.

## Verification
- [ ] Two Swarm processes can detect each other's presence via the DB.
- [ ] An event emitted by Swarm A is visible in the event log of Swarm B.
