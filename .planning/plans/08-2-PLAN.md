# Plan 08-2: Coordinator & Agent Integration

## Objective
Enable the `Coordinator` to assign skills to agents and inject them into the runtime.

## Tasks
1. **Update AgentConfig**: Add `skills: List[str]` field to `AgentConfig` in `src/runtimes/base.py`.
2. **Skill Injection**: In `Coordinator.assign_task`, lookup assigned skills and merge their tools/prompts into the `AgentConfig`.
3. **Runtime Support**: Ensure `ClaudeCodeRuntime` and others use the merged `allowed_tools` list.
4. **Task Schema**: Update `TaskPacket` to support optional skill requirements.

## Verification
- [ ] Agent spawned with `web_research` skill has `web_search` and `web_fetch` in its `allowed_tools`.
- [ ] Skill instructions are present in the final system prompt.
