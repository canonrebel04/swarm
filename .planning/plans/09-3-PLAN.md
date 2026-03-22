# Plan 09-3: Experience Injection

## Objective
Inject historical lessons into new agent sessions to prevent repeating past errors.

## Tasks
1. **Retrieval**: Implement `db.get_lessons_for_role(role)` to fetch synthesized lessons.
2. **Injection**: Update `Coordinator.assign_task` to fetch and append these lessons to the system prompt or task description.
3. **Format**: Use a clear "## PAST EXPERIENCE" header to anchor the model's attention.
4. **Pruning**: Only inject the top 3 most relevant or recent lessons to save context.

## Verification
- [ ] Agent spawned as Developer receives specific lessons related to past Developer failures.
- [ ] System prompt remains concise and well-structured with the added experience.
