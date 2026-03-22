# Plan 09-2: Reflection Agent Logic

## Objective
Implement an internal agent that synthesizes critiques into reusable lessons.

## Tasks
1. **Definition**: Create `src/agents/definitions/reflection.md`.
2. **Analysis Logic**: Implement a method in `Coordinator` (or a new service) to query recent critiques and spawn a Reflection agent.
3. **Synthesis**: The Reflection agent identifies patterns (e.g., "Developer often forgets imports") and writes a concise "Lesson" back to the DB.
4. **Trigger**: Add a manual trigger in the `Supervisor` or automated trigger every 5 rejections.

## Verification
- [ ] Reflection agent successfully processes multiple critiques and produces a summarized lesson.
- [ ] Lessons are correctly stored and associated with the relevant roles.
