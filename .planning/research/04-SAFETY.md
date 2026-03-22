# Research: Role Safety Enforcement (Tool Policy & FS Controls)

## Overview
Phase 4 focusing on hardening the Swarm environment by restricting what agents can do at the runtime level, beyond just system prompt instructions.

## Tool Policy Enforcement Patterns

### Claude Code
- **Method:** Use `--allowedTools` and `--disallowedTools` flags.
- **Implementation:** The `ClaudeCodeRuntime` should map role-based tool lists to these flags.
- **Example:** Scout role gets `--allowedTools "Read" "Search"` and `--disallowedTools "Bash"`.

### Mistral Vibe
- **Method:** Built-in agents (`--agent`) or disabling specific tools in agent TOML.
- **Implementation:** Map roles to vibe agents (already partially done) and use `--enabled-tools` if available in the version being used.

### Gemini CLI / Codex / OpenCode
- **Method:** Most support some form of tool restriction or sandbox.
- **Implementation:** Default to `--read-only` or equivalent where possible for Scouts/Reviewers.

## Filesystem Access Controls

### Worktree Strategy
- **Mechanism:** Swarm already uses `git worktree` for isolation.
- **Harden:** Ensure the `AgentRuntime` always sets the `cwd` and workdir to the specific worktree path.
- **Restrict:** Use OS-level permissions or runtime-specific sandbox flags (like Codex's `--sandbox`) to prevent directory traversal.

## Structured Output Validation
- **Mechanism:** Agents must return a JSON block at the end of their task.
- **Implementation:** The `Coordinator` or `AgentManager` should validate the last output line against a schema before marking a task as "done".
- **Retry:** If validation fails, use the `Supervisor` nudge mechanism.

## Supervisor Intervention Workflow
- **Actions:** Pause, Nudge, Retry, Kill.
- **Trigger:** Manual user action in TUI or automated `AntiDriftMonitor` alert.
- **Implementation:** Standardize the `AgentRuntime.kill()` and `AgentRuntime.send_message()` (nudge) interfaces.
