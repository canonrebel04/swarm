# Plan 12-1: Logical Conflict Detection

## Objective
Implement early detection of semantic conflicts in the `Coordinator`.

## Tasks
1. **Overlap Scanner**: Implement `_scan_for_overlaps()` in `Coordinator` to check `files_in_scope` and task descriptions for collisions.
2. **Conflict Flagging**: Add `potential_conflict: bool` and `conflict_details: str` to `TaskPacket`.
3. **Queue Pause**: Update `process_task_queue` to skip tasks flagged with a potential conflict until resolved.
4. **Overseer Update**: Update Overseer prompt to consider scope overlap during decomposition.

## Verification
- [ ] Unit test: Two tasks modifying `auth.py` simultaneously are correctly flagged.
- [ ] Blocked tasks do not spawn until the conflict flag is cleared.
