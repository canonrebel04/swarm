# Phase 8 Context: Custom Skills Registry

## Overview
Phase 8 introduces a formal registry for "Skills" — reusable sets of tools, instructions, and examples that can be assigned to agents regardless of their primary role.

## Implementation Decisions

### Skill Data Model
- **Identity:** Name, Version, Description.
- **Tools:** List of required tools (e.g., `web_search`, `vector_query`).
- **Instructions:** Markdown-based system prompt additions.
- **Constraints:** Any specific role-like may/may_not rules specific to the skill.

### Storage & Registry
- **Directory:** `src/skills/definitions/*.yaml` and `*.md`.
- **Registry:** `src/skills/registry.py` (singleton).
- **Handoff:** Agents can be spawned with one or more skills attached.

### Dynamic Injection
- The `Coordinator` will merge role contracts with skill definitions during `AgentConfig` creation.
- Runtimes (like Claude Code) will receive the combined tool allowlist.

## Gray Areas
- Should skills have their own "Handoff" rules? *Decision: No, handoff is a role-level concern. Skills only provide capabilities.*
- Can skills be runtime-specific? *Decision: No, aim for provider-agnostic skill definitions.*
