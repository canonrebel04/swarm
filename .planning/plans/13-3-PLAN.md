# Plan 13-3: Shared Resource Management

## Objective
Prevent multi-swarm collisions through shared locking.

## Tasks
1. **Global Lock Table**: Create `resource_locks` in `SwarmDB` (fields: resource_path, swarm_id, expires_at).
2. **Locking Service**: Implement `GlobalResourceLocker` to acquire and release file-level locks across Swarms.
3. **Coordinator Integration**: Update `_scan_for_overlaps` to check for locks held by other Swarms.
4. **Safety Heartbeat**: Implement automatic lock expiration to prevent deadlocks if a Swarm process crashes.

## Verification
- [ ] Swarm A cannot start a task on `auth.py` while Swarm B holds a lock on it.
- [ ] Locks are automatically released when a Swarm completes its task or times out.
