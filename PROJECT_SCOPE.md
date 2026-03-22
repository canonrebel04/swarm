# Swarm — Project Scope & Best Practices

> **Project Codename:** Swarm  
> **Inspired by:** [Overstory](https://github.com/jayminwest/overstory)  
> **Goal:** A provider-agnostic multi-agent orchestration TUI with first-class support for the most popular coding-agent CLIs, including Claude Code, Codex CLI, Gemini CLI, OpenCode, Goose, Cline CLI, Qodo Gen CLI, Mistral Vibe (`vibe`), Hermes-based local agents, and OpenClaw.

---

## 1. Vision & Core Values
Swarm exists to provide a visible, persistent, and coordinated interface for multiple autonomous coding agents. Unlike single-agent TUIs (like Claude Code or Aider), Swarm treats these tools as "workers" in a fleet, orchestrated by a high-level "Overseer."

### Core Values:
- **Provider Agnostic:** Support any coding agent that provides a CLI.
- **Role Specificity:** Force agents into narrow roles (Scout, Developer, Builder, Tester) to minimize drift and cost.
- **Persistence:** All agent messages and events are stored in a central SQLite database.
- **Visibility:** A rich TUI that shows the status and output of the entire fleet simultaneously.
- **Safety First:** Role-locking and drift detection ensure agents don't wander off-task.

---

## 2. High-Level Architecture
Swarm is built as a hierarchical orchestration system.

### The Hierarchy:
1.  **User:** Provides the high-level objective via the TUI.
2.  **Overseer:** An LLM-backed central brain that decomposes the objective into tasks and assigns them to the fleet.
3.  **Coordinator:** The internal logic that manages agent lifecycles, worktrees, and data flow.
4.  **Agent Fleet:** A collection of specialized worker agents (Claude Code, Gemini, etc.) bound by specific roles.

---

## 3. TUI Layout (Conceptual)
```text
┌────────────────────────────────────────────────────────────────────┐
│                             Swarm TUI                              │
├──────────────────────────────────┬─────────────────────────────────┤
│        OVERSEER CHAT             │          AGENT FLEET            │
│  [User] build feature X          │  lead-1      running   claude   │
│  [Overseer] spawning lead        │  builder-1   running   vibe     │
│  [Overseer] scout first          │  tester-1    queued    gemini   │
│  [Overseer] nudging builder      │  reviewer-1  stalled   codex    │
│                                  │  merger-1    waiting   opencode │
├──────────────────────────────────┴─────────────────────────────────┤
│                  SELECTED AGENT OUTPUT / EVENTS                    │
│  [builder-1] Running pytest...                                     │
│  [builder-1] Fix applied to src/auth.py                            │
│  [System] builder-1 reached 80% cost cap. Nudging...               │
└────────────────────────────────────────────────────────────────────┘
```

---

## 4. Key Components

### Runtime Adapters (`src/runtimes/`)
Standardized interfaces for different agent CLIs.
- `base.py`: The `AgentRuntime` abstract base class.
- `claude_code.py`
- `gemini.py`
- `codex.py`
- `opencode.py`
- `vibe.py`
- `hermes.py`
- `echo.py` (for testing)

### Orchestration (`src/orchestrator/`)
- `agent_manager.py`: Manages the spawning, tracking, and killing of agent processes.
- `coordinator.py`: Implements the task assignment logic and handoff rules.
- `worktree_manager.py`: Ensures every agent operates in an isolated `git worktree`.

### Messaging (`src/messaging/`)
- `db.py`: SQLite schema for messages, events, and fleet status.
- `event_bus.py`: Asyncio-based event system for TUI updates and internal coordination.

### Roles (`src/roles/`)
- `registry.py`: Map of available roles and their required/forbidden actions.
- `contracts/`: YAML definitions of role boundaries (e.g., "Scout cannot write files").

---

## 5. Agent Capability Matrix

| Runtime | Best Role Fit | Execution Style |
| :--- | :--- | :--- |
| **Claude Code** | Developer, Lead | Interactive / Multi-turn |
| **Codex CLI** | Scout, Builder | Task-first |
| **Gemini CLI** | Scout, Tester | Task-first |
| **OpenCode** | Developer, Builder | Interactive |
| **Mistral Vibe** | Builder, Developer | Task-first |
| **Hermes (Local)** | Scout, Tester | Task-first |

---

## 6. Implementation Strategy: "Role Locking"
To prevent "agent drift" (where an agent starts performing tasks outside its scope), Swarm implements:
1.  **Identity Anchoring:** Every agent is spawned with a system prompt footer that reiterates its role and forbidden actions.
2.  **Tool Policy Enforcement:** The `AgentRuntime` limits which CLI flags are passed (e.g., passing `--read-only` to a Scout).
3.  **Anti-Drift Monitor:** The `Monitor` agent periodically inspects worker outputs for signs of role violation.

---

## 7. Persistence & State
- **Database:** `~/.swarm/messages.db` (SQLite)
- **Tables:** `agents`, `tasks`, `messages`, `events`, `costs`.
- **WAL Mode:** Enabled for high-concurrency async access.

---

## 8. Development Environment
- **Language:** Python 3.12+
- **Frontend:** Textual (TUI framework)
- **Async:** `asyncio` + `aiosqlite`
- **Build System:** Poetry

---

## 9. Security & Safety
- **Worktree Isolation:** Critical to prevent agents from clobbering each other's files.
- **Git Commit Anchors:** Automatic `git commit` after every successful agent task completion.
- **Cost Caps:** Hard and soft limits on tokens/dollars per agent session.

---

## 10. Role Definitions (Detailed)

### Scout
- **Mission:** Fact-finding and exploration.
- **Allowed:** Read files, list directories, grep, find, web search.
- **Forbidden:** Write files, delete files, git commit, git push.

### Developer
- **Mission:** Complex implementation and reasoning.
- **Allowed:** Edit files, read files, run tests, plan architecture.
- **Forbidden:** Merge to main, push to remote.

### Builder
- **Mission:** Fast execution of well-defined tasks.
- **Allowed:** Write files, run build commands, install dependencies.
- **Forbidden:** Multi-file architectural changes.

### Tester
- **Mission:** Validation and quality assurance.
- **Allowed:** Write test files, run pytest/coverage, document bugs.
- **Forbidden:** Modify production source code.

### Reviewer
- **Mission:** Quality audit.
- **Allowed:** Read changes, provide feedback, issue approve/reject verdict.
- **Forbidden:** Modify any files.

### Merger
- **Mission:** Branch finalization.
- **Allowed:** Resolve git conflicts, merge branches, delete temp branches.
- **Forbidden:** Write new feature code.

### Monitor
- **Mission:** Fleet observability.
- **Allowed:** Read logs, track agent state, detect stalls/drift.
- **Forbidden:** Modify any product or project files.

---

## 11. Coordination Logic

### The Handoff Chain
`User request` -> `Overseer` -> `Coordinator` -> `Lead` -> `Workers` (Scout/Dev/Build/Test) -> `Reviewer` -> `Merger` -> `Done`.

### Event-Driven Flow
1. `AgentSpawned`
2. `TaskAssigned`
3. `OutputReceived`
4. `ToolCalled`
5. `TaskCompleted`
6. `HandoffTriggered`

---

## 12. Command Line Interface
- `swarm run`: Launches the TUI.
- `swarm init`: Set up a new swarm project in the current directory.
- `swarm doctor`: Check for dependencies (binary versions, API keys).
- `swarm logs`: Export/view the SQLite message log.

---

## 13. Future Roadmap (Milestone 2+)
- **Extended Adapters:** Goose, Cline, Qodo.
- **Custom Skills:** Registry for user-defined agent skills.
- **Meta-Learning:** Agents that improve their own system prompts based on Reviewer feedback.
- **Cloud Deployment:** Orchestrate agents running on remote servers or ephemeral containers.

---

## 14. Best Practices for Developers
- **Async Everywhere:** Never use blocking `subprocess.run`; always use `asyncio.create_subprocess_exec`.
- **Atomic Operations:** Keep agent tasks small and verifiable.
- **Type Safety:** Use Pydantic models for configuration and state.
- **Clean Handoffs:** Ensure the "context package" passed between agents is minimal but sufficient.

---

## 15. Known Constraints
- Agents must have a CLI interface.
- Support for streaming output is highly prioritized but not mandatory for basic integration.
- Concurrent execution is limited by local CPU/RAM and API rate limits.

---

## 16. Troubleshooting
- `swarm doctor` is the first line of defense.
- Check `~/.swarm/logs/system.log` for orchestrator-level failures.
- Use the "Event Log" panel in the TUI to trace agent lifecycle issues.

---

## 17. Milestone Roadmap

### Phase 1 — Foundation
- [x] Project scaffolding
- [x] AgentRuntime base interface
- [x] Role registry + role contracts
- [x] SQLite event/message bus
- [x] Git worktree manager
- [x] Fleet status model

### Phase 2 — Core Roles
- [x] Scout role definition + contract
- [x] Developer role definition + contract
- [x] Builder role definition + contract
- [x] Tester role definition + contract
- [x] Orchestrator role definition + contract
- [x] Coordinator role definition + contract
- [x] Supervisor role definition + contract
- [x] Lead role definition + contract
- [x] Reviewer role definition + contract
- [x] Merger role definition + contract
- [x] Monitor role definition + contract

### Phase 3 — Runtime Adapters v1
- [x] Claude Code adapter
- [x] Codex CLI adapter
- [x] Gemini CLI adapter
- [x] OpenCode adapter
- [x] Mistral Vibe adapter
- [x] Hermes adapter
- [x] Echo adapter

### Phase 4 — Role Safety
- [x] Role locking mechanism
- [x] Anti-drift detection system
- [ ] Tool policy enforcement
- [ ] Filesystem access controls
- [ ] Structured output validation
- [ ] Supervisor intervention workflow
- [ ] Drift detection alerts

### Phase 5 — TUI
- [x] Overseer chat panel
- [x] Fleet panel
- [x] Selected agent output
- [x] Event log
- [x] Role contract viewer
- [x] Drift/stall warnings
- [x] Nudge / retry / kill actions

### Phase 6 — Extended Adapters
- [ ] Goose adapter
- [ ] Cline CLI adapter
- [ ] Qodo Gen CLI adapter
- [ ] OpenClaw experimental adapter

### Phase 7 — Polish
- [ ] `swarm init`
- [ ] `swarm doctor`
- [ ] Replay logs
- [ ] Merge queue
- [ ] README
- [ ] Demo GIF / asciinema
