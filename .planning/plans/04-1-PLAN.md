# Plan 04-1: Tool Policy Enforcement

## Objective
Harden agent runtimes by passing explicit tool restriction flags based on agent roles.

## Tasks
1. **Update ClaudeCodeRuntime**: Map `allowed_tools` from `AgentConfig` to `--allowedTools` and `--disallowedTools`.
2. **Update VibeRuntime**: Use `--enabled-tools` or specific agent profiles to restrict capabilities for Scouts/Reviewers.
3. **Update CodexRuntime**: Ensure `--sandbox` level is correctly set based on role (already partially implemented).
4. **Update AgentConfig**: Add `read_only` and `allowed_tools` defaults per role in the `Coordinator`.

## Verification
- [ ] Claude spawned as Scout has `Bash` disallowed in CLI flags.
- [ ] Vibe spawned as Reviewer has restricted toolset.
- [ ] Integration tests verify that an agent attempting a blocked tool fails at the runtime level.
