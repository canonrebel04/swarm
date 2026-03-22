# Plan 09-1: Structured Feedback Storage

## Objective
Implement the database schema and logic to capture and store detailed agent critiques.

## Tasks
1. **DB Schema**: Add `experience_logs` table to `src/messaging/db.py` (fields: role, task_title, status, critique, lessons_learned, timestamp).
2. **Reviewer Update**: Modify `src/agents/definitions/reviewer.md` to require a `critique` field in the handoff JSON.
3. **Capture Logic**: Update `Coordinator.complete_task` to store the `critique` from Reviewer handoffs into the DB.

## Verification
- [ ] `experience_logs` table exists and persists data.
- [ ] Reviewer output with `critique` is successfully captured by the Coordinator.
