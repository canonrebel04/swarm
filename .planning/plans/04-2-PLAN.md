# Plan 04-2: Structured Output Validation

## Objective
Ensure all agents return a valid JSON handoff block before a task is marked as "done".

## Tasks
1. **Define Schema**: Define the expected JSON handoff schema (role, status, summary, files_changed, handoff_to).
2. **Update Coordinator**: Add a validation step in `complete_task` that parses the agent's final output for the JSON block.
3. **Implement Nudge on Failure**: If JSON is missing or invalid, automatically nudge the agent using `runtime.send_message()` to provide the handoff block.
4. **Update AgentManager**: Ensure final output is captured accurately from streaming runtimes.

## Verification
- [ ] Task completion fails if JSON block is missing.
- [ ] Automated nudge successfully recovers missing JSON in a test scenario.
