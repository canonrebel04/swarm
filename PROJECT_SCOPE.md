# Swarm — Project Scope & Best Practices

> **Project Codename:** Swarm  
> **Inspired by:** [Overstory](https://github.com/jayminwest/overstory)  
> **Goal:** A provider-agnostic multi-agent orchestration TUI with first-class support for the most popular coding-agent CLIs, including Claude Code, Codex CLI, Gemini CLI, Aider, OpenHands CLI, OpenCode, Goose, Cline CLI, Qodo Gen CLI, Mistral Vibe (`vibe`), Hermes-based local agents, and OpenClaw.

---

## 1. Problem Statement

Overstory is one of the strongest references for multi-agent orchestration, but its implementation and defaults are still centered around its own supported runtime stack and workflow assumptions.

Key gaps that Swarm addresses:

- I want support for **all major coding-agent CLIs**, not only one or two.
- I want a visible **overseer + worker fleet interface**, not only a command-driven orchestration flow.
- I want **role-stable agents** that stay inside their assigned role instead of drifting into other jobs.
- I want **provider/runtime portability**, including cloud and local models.
- I want an architecture where **new agent runtimes can be added without rewriting orchestration logic**.
- I want a clean path for both **interactive terminal agents** and **headless CI/task agents**.

---

## 2. Core Vision

A **terminal-first multi-agent orchestration system** where:

1. An **Overseer** maintains the top-level conversation and project objective.
2. The Overseer **decomposes work into role-bound sub-tasks**.
3. The Overseer **spawns sub-agents** using different runtimes depending on task fit.
4. The TUI shows **both layers simultaneously** — Overseer chat, active agents, current task, status, runtime, and recent output.
5. The Overseer can **nudge, pause, retry, replace, or terminate** stalled agents.
6. Every agent runs with a **locked role contract** so it cannot silently become a different type of agent.
7. The system supports both **single-project swarms** and eventually **multi-project orchestration**.

---

## 3. Build vs Fork Decision

### Option A — Fork Overstory

| Pros | Cons |
|------|------|
| Mature architecture ideas already proven | Deeply tied to its own runtime assumptions and project structure |
| Good reference for role hierarchy, watchdogs, worktrees, and merge flow | Untangling runtime-specific behavior will cost time |
| Strong orchestration concepts | Harder to redesign around a new UI and broader runtime support |
| Existing multi-agent patterns are useful to study | You inherit design decisions you may not want long-term |

### Option B — Build from Scratch ✅ (Recommended)

| Pros | Cons |
|------|------|
| Full control over runtime adapters from day one | More initial implementation work |
| Can design the TUI around overseer + fleet visibility | Must build core orchestration pieces yourself |
| Can make role enforcement a first-class concept | Need to define your own contracts, guards, and state model |
| Easier to support many agent CLIs consistently | Less out-of-the-box behavior |

**Verdict:** Build from scratch, but borrow Overstory’s best ideas: role-based agents, worktree isolation, coordinator hierarchy, mail/state tracking, merge stages, and watchdog health checks.

---

## 4. Recommended Tech Stack

| Layer | Recommendation | Reason |
|-------|---------------|--------|
| **Language** | Python 3.12+ | Fast iteration, great subprocess support, good async ecosystem |
| **TUI Framework** | [Textual](https://github.com/Textualize/textual) | Best fit for live split-pane orchestration UI |
| **CLI Entry Point** | [Typer](https://typer.tiangolo.com/) | Clean command structure, easy UX |
| **Process Management** | `asyncio` + `asyncio.subprocess` | Non-blocking runtime control |
| **Optional Session Control** | `tmux` via `libtmux` | Useful for agents that need pseudo-interactive control |
| **Messaging / State** | SQLite (WAL mode) via `aiosqlite` | Durable, simple, fast local coordination state |
| **Validation / Config** | Pydantic + YAML | Structured configs and role contracts |
| **Worktree Isolation** | `git worktree` | One agent per branch/worktree |
| **Logs / Events** | NDJSON | Easy streaming and replay |
| **Policy Engine** | Internal rules layer | Needed for role locking, tool filtering, and access boundaries |

---

## 5. Architecture Design

```text
┌────────────────────────────────────────────────────────────────────┐
│                        Swarm TUI                          │
├──────────────────────────────┬─────────────────────────────────────┤
│        OVERSEER CHAT         │          AGENT FLEET                │
│  [User] build feature X      │  lead-1       running   claude      │
│  [Overseer] spawning lead    │  builder-1    running   aider       │
│  [Overseer] scout first      │  tester-1     queued    gemini      │
│  [Overseer] nudging builder  │  reviewer-1   stalled   codex       │
│                              │  merger-1     waiting   opencode    │
├──────────────────────────────┴─────────────────────────────────────┤
│                  SELECTED AGENT OUTPUT / EVENTS                    │
│  builder-1: reading files...                                       │
│  builder-1: edited auth.py                                         │
│  builder-1: ready for tests                                        │
└────────────────────────────────────────────────────────────────────┘
```

### Core Components

```text
swarm/
  src/
    main.py
    config.py
    cli/
      app.py
      commands/
        init.py
        run.py
        status.py
        inspect.py
        nudge.py
        stop.py
        doctor.py
        roles.py
        runtimes.py
    tui/
      app.py
      panels/
        overseer_chat.py
        agent_fleet.py
        agent_output.py
        event_log.py
        role_view.py
    orchestrator/
      overseer.py
      coordinator.py
      dispatcher.py
      agent_manager.py
      watchdog.py
      merge_manager.py
      completion.py
    runtimes/
      base.py
      claude_code.py
      codex.py
      gemini_cli.py
      aider.py
      openhands.py
      opencode.py
      goose.py
      cline.py
      qodo.py
      mistral_vibe.py
      hermes.py
      openclaw.py
      registry.py
      capabilities.py
    roles/
      registry.py
      contracts.py
      guards.py
      prompts.py
      policies.py
    messaging/
      db.py
      protocol.py
      bus.py
      events.py
    worktree/
      manager.py
    logging/
      logger.py
      replay.py
    agents/
      definitions/
        orchestrator.md
        coordinator.md
        supervisor.md
        lead.md
        scout.md
        developer.md
        builder.md
        tester.md
        reviewer.md
        merger.md
        monitor.md
  config.yaml
  pyproject.toml
  README.md
  AGENTS.md
```

---

## 6. Supported Runtime Strategy

Swarm should support runtimes in **tiers**, not claim identical parity for every tool on day one.

### Tier 1 — Must Support in v1

| Runtime | Why it matters | Mode |
|--------|----------------|------|
| **Claude Code** | One of the leading coding agents | Interactive + task |
| **Codex CLI** | Core target runtime | Interactive + task |
| **Gemini CLI** | Core target runtime | Interactive + task |
| **Aider** | Popular terminal-native coding tool with repo awareness | Task-first |
| **OpenHands CLI** | Strong agentic coding workflow and headless fit | Task-first |
| **OpenCode** | Built as a terminal coding agent with agent concepts | Interactive + task |
| **Mistral Vibe (`vibe`)** | Important for Mistral-based workflows | Task-first / resumable |
| **Hermes (Ollama / llama.cpp)** | Local/private model support | Task-first |

### Tier 2 — High-Value After v1

| Runtime | Why it matters | Mode |
|--------|----------------|------|
| **Goose** | Strong CLI agent story and tool integrations | Task-first |
| **Cline CLI** | Terminal-native coding agent, promising for orchestration | Interactive + task |
| **Qodo Gen CLI** | Agent framework orientation and CI angle | Task-first |
| **OpenClaw** | Interesting agent/gateway system, but not primarily a coding CLI | Task-first |

### Tier 3 — Nice-to-Have / Experimental

- Cursor CLI
- Copilot CLI-style interfaces
- Local wrappers around custom MCP-capable agents
- Custom shell-based or API-backed internal agents

### Runtime Support Levels

| Level | Meaning |
|------|---------|
| **Level 1** | Run task, stream output, capture completion/failure |
| **Level 2** | Resume, nudge, interrupt, retry |
| **Level 3** | Full role-safe integration with structured status, isolation, and tool policy |

---

## 7. AgentRuntime Interface (Best Practice)

The most important architectural decision is the **runtime adapter interface**. Design this first.

```python
# src/runtimes/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator

@dataclass
class AgentConfig:
    name: str
    role: str
    task: str
    worktree_path: str
    model: str
    runtime: str
    system_prompt_path: str
    allowed_tools: list[str] = field(default_factory=list)
    blocked_tools: list[str] = field(default_factory=list)
    read_only: bool = False
    can_spawn_children: bool = False
    extra_env: dict[str, str] = field(default_factory=dict)

@dataclass
class AgentStatus:
    name: str
    role: str
    state: str          # queued | running | stalled | done | error | blocked
    current_task: str
    runtime: str
    last_output: str
    pid: int | None

@dataclass
class RuntimeCapabilities:
    interactive_chat: bool
    headless_run: bool
    resume_session: bool
    streaming_output: bool
    tool_allowlist: bool
    sandbox_support: bool
    agent_profiles: bool
    parallel_safe: bool

class AgentRuntime(ABC):
    @property
    @abstractmethod
    def runtime_name(self) -> str:
        ...

    @property
    @abstractmethod
    def capabilities(self) -> RuntimeCapabilities:
        ...

    @abstractmethod
    async def spawn(self, config: AgentConfig) -> str:
        ...

    @abstractmethod
    async def send_message(self, session_id: str, message: str) -> None:
        ...

    @abstractmethod
    async def get_status(self, session_id: str) -> AgentStatus:
        ...

    @abstractmethod
    async def stream_output(self, session_id: str) -> AsyncIterator[str]:
        ...

    @abstractmethod
    async def kill(self, session_id: str) -> None:
        ...
```

---

## 8. Agent Role System

This project needs an **explicit role system**, not just “different prompts.” A role is a contract with identity, permissions, expected outputs, and forbidden behaviors.

### Base Role Set

This keeps the Overstory-style hierarchy while adding the two roles you explicitly want: **developer** and **tester**.

| Role | Purpose | Access | Can Spawn? |
|------|---------|--------|------------|
| **Orchestrator** | Multi-project or meta-coordinator | Read-only | Yes |
| **Coordinator** | Break goals into work, assign agents, track progress | Read-only | Yes |
| **Supervisor** | Fleet oversight, escalation handling, intervention | Read-only | Limited |
| **Lead** | Team-level coordinator for a workstream | Read-mostly | Yes |
| **Scout** | Explore code, read docs, inspect architecture, gather facts | Read-only | No |
| **Developer** | Implement scoped code changes with higher reasoning focus | Read-write | No |
| **Builder** | Fast execution-oriented code editing and implementation | Read-write | No |
| **Tester** | Run tests, add tests, validate behavior, reproduce bugs | Read-write (tests only preferred) | No |
| **Reviewer** | Review code, detect issues, reject bad outputs | Read-only | No |
| **Merger** | Merge approved work, resolve safe conflicts, finalize branch state | Read-write | No |
| **Monitor** | Detect stalls, failures, drift, and unhealthy sessions | Read-only | No |

### Role Relationships

```text
Orchestrator
  -> Coordinator
      -> Supervisor
          -> Lead
              -> Scout
              -> Developer
              -> Builder
              -> Tester
              -> Reviewer
              -> Merger
      -> Monitor
```

### Why Both Developer and Builder?

Use both, but differentiate them.

| Role | Best Use |
|------|----------|
| **Developer** | Complex implementation requiring planning, reasoning, architecture-sensitive edits |
| **Builder** | Faster execution on bounded code tasks, refactors, small feature slices |
| **Tester** | Verification, regression checks, test writing, repro scripts |

That gives you cleaner delegation:
- Scout finds facts.
- Lead decomposes.
- Developer handles complex implementation.
- Builder handles straightforward edit-heavy work.
- Tester validates.
- Reviewer critiques.
- Merger lands changes.
- Monitor watches fleet health.

---

## 9. Role Locking and Anti-Drift

This is a core design requirement: **the main AI must not be able to deploy a role and then let it drift into another job silently**.

### Best Practice: Role = Prompt + Policy + Access + Validation

Each spawned agent must receive:

1. A **role ID**
2. A **role contract**
3. A **system prompt template**
4. A **tool allowlist**
5. A **filesystem policy**
6. A **spawn policy**
7. A **completion schema**
8. A **drift detector**

### Role Contract Example

```yaml
# roles/contracts/builder.yaml
role: builder
identity: "You are Builder, an implementation agent."
mission: "Make scoped code changes only for the assigned task."
may:
  - read_repo
  - edit_code
  - run_local_tests
  - write_small_docs
may_not:
  - redefine_requirements
  - review_own_work_as_final_authority
  - merge_branches
  - spawn_agents
  - modify_global_policy
required_outputs:
  - summary
  - files_changed
  - risks
  - test_status
handoff_to:
  - tester
  - reviewer
```

### Enforcement Layers

#### 1. Prompt-Level Role Anchoring
Every role prompt should repeat:
- who the agent is,
- what it is allowed to do,
- what it must not do,
- who it hands off to.

#### 2. Runtime-Level Tool Restrictions
Examples:
- Scout cannot use edit tools.
- Reviewer cannot write code.
- Merger cannot invent new implementation tasks.
- Monitor cannot modify product code.
- Lead can delegate but not directly implement except in explicitly allowed fallback mode.

#### 3. Filesystem Policy
Examples:
- Scout and Reviewer mount repo read-only where possible.
- Tester may write only in test directories, logs, repro scripts, or explicitly allowed temp paths.
- Merger can touch merge metadata and target branch state.
- Developer and Builder get normal task-scoped worktree write access.

#### 4. Task-Type Validation
The coordinator tags each task with a required role. If a Builder starts producing review language or a Reviewer attempts edits, the watchdog flags drift.

#### 5. Output Schema Validation
Each role returns structured output. Example:
- Scout returns findings and cited evidence.
- Builder returns changed files and implementation notes.
- Tester returns commands run, pass/fail, and repro info.
- Reviewer returns verdict and concerns.
- Merger returns merge result and conflict summary.

#### 6. Drift Detection
Monitor or Supervisor checks for:
- wrong tool usage,
- forbidden file writes,
- self-reassignment language,
- role-inconsistent outputs,
- unexpected child spawning,
- repeated instruction override attempts.

### Hard Rule

**Agents never self-upgrade roles.**  
If a Scout decides code must be changed, it requests a Builder or Developer.  
If a Builder thinks review is needed, it hands off to Reviewer.  
If a Reviewer finds implementation gaps, it sends work back instead of fixing them directly.

---

## 10. Agent Definitions

Each role gets its own definition file.

```text
src/agents/definitions/
  orchestrator.md
  coordinator.md
  supervisor.md
  lead.md
  scout.md
  developer.md
  builder.md
  tester.md
  reviewer.md
  merger.md
  monitor.md
```

### Definition Template

```markdown
# Role: Builder

## Identity
You are Builder, an implementation-focused coding agent.

## Primary Goal
Make the assigned code changes cleanly and minimally.

## Allowed Actions
- Read repository files
- Edit source code
- Run local validation commands approved for this task
- Produce a structured handoff for tester/reviewer

## Forbidden Actions
- Do not merge branches
- Do not redefine the task
- Do not spawn new agents
- Do not claim review is complete
- Do not modify unrelated files

## Success Criteria
- Task scope satisfied
- Changes remain minimal
- Output includes files changed, validation run, risks, and handoff notes

## Handoff
Send work to Tester or Reviewer when implementation is complete.
```

---

## 11. Overseer and Delegation Rules

The Overseer should not dispatch arbitrary prompts. It should dispatch **typed tasks**.

### Task Packet

```python
@dataclass
class TaskPacket:
    id: str
    title: str
    description: str
    role_required: str
    runtime_preference: list[str]
    priority: str
    files_in_scope: list[str]
    acceptance_criteria: list[str]
    parent_agent: str | None
```

### Delegation Rules

- **Scout** first when facts are missing.
- **Lead** when one issue likely needs multiple workers.
- **Developer** for architecture-sensitive or multi-file changes.
- **Builder** for bounded implementation tasks.
- **Tester** after implementation or for bug reproduction.
- **Reviewer** before merge on non-trivial changes.
- **Merger** only after approval conditions are met.
- **Monitor** runs continuously or on interval.

### Example Flow

```text
User request
  -> Coordinator
      -> Scout (map code + risks)
      -> Lead (split work)
          -> Developer (complex change)
          -> Builder (small subtask)
          -> Tester (run validations)
          -> Reviewer (judge quality)
      -> Merger
      -> Monitor keeps watching all sessions
```

---

## 12. Runtime Adapters Overview

### Runtime Matrix

| Runtime | Category | Notes |
|--------|----------|------|
| **Claude Code** | Premium coding agent | First-class support target |
| **Codex CLI** | Premium coding agent | First-class support target |
| **Gemini CLI** | Premium coding agent | First-class support target |
| **Aider** | Terminal coding tool | Great repo-aware implementation agent |
| **OpenHands CLI** | Autonomous coding agent | Strong headless/task workflow |
| **OpenCode** | Terminal coding agent | Good fit for open agent architecture |
| **Goose** | Open-source CLI agent | Strong tool-oriented flow |
| **Cline CLI** | Terminal coding agent | Good candidate for role-based orchestration |
| **Qodo Gen CLI** | Agent framework CLI | Good for CI and structured tasks |
| **Mistral Vibe (`vibe`)** | Programmatic CLI | Strong Mistral support |
| **Hermes via Ollama / llama.cpp** | Local model runtime | Privacy-friendly local support |
| **OpenClaw** | Agent gateway platform | Experimental coding fit |

### Core Adapter Requirement

Every adapter must implement:

- spawn task
- stream output
- capture structured completion
- detect stall/error
- send follow-up or resume message when supported
- expose runtime capabilities
- respect role/tool restrictions as much as the runtime allows

---

## 13. Mistral Vibe Notes

`vibe` already exposes a useful programmatic mode with `-p`, output formats including `streaming`, tool filtering via `--enabled-tools`, agent profiles via `--agent`, workdir switching via `--workdir`, and resume support via `--resume`.

### Recommended Use
- Use `-p` for headless runs.
- Use `--output streaming` for live event feed.
- Use `--enabled-tools` to align runtime behavior with role policy.
- Use `--resume` for nudges or follow-up turns.

### Good Role Fits
- Scout
- Builder
- Developer
- Reviewer (if tool-restricted)
- Tester

---

## 14. OpenClaw Notes

OpenClaw is interesting, but it is not primarily a coding-agent CLI. Treat it as an **experimental adapter**.

### Recommended Use
- Profile-isolated agents via `--profile`
- Gateway-backed sessions
- ACP exploration for richer control

### Good Role Fits
- Monitor
- Supervisor
- Experimental task agents
- Notification / external workflow bridges

---

## 15. TUI Layout Best Practices

```python
# src/tui/app.py
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer
from .panels.overseer_chat import OverseerChat
from .panels.agent_fleet import AgentFleet
from .panels.agent_output import AgentOutput

class SwarmApp(App):
    CSS = """
    Screen { layout: vertical; }
    #main { height: 70%; }
    OverseerChat { width: 45%; border: solid green; }
    AgentFleet { width: 55%; border: solid cyan; }
    AgentOutput { height: 30%; border: solid yellow; }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            yield OverseerChat()
            yield AgentFleet()
        yield AgentOutput()
        yield Footer()
```

### Required TUI Views

- Overseer conversation
- Fleet status table
- Current task per agent
- Runtime per agent
- Selected agent live output
- Role contract summary
- Alerts for stall, drift, forbidden action, completion, and merge readiness

---

## 16. Config File Design

```yaml
# config.yaml

overseer:
  runtime: claude-code
  model: sonnet
  system_prompt: src/agents/definitions/coordinator.md

agents:
  max_concurrent: 8
  stall_timeout_seconds: 120
  drift_check_seconds: 20
  require_role_contract: true
  require_structured_output: true
  default_handoff: reviewer

roles:
  enabled:
    - orchestrator
    - coordinator
    - supervisor
    - lead
    - scout
    - developer
    - builder
    - tester
    - reviewer
    - merger
    - monitor
  prompts_dir: src/agents/definitions
  contracts_dir: src/roles/contracts
  strict_locking: true
  forbid_self_reassignment: true

runtimes:
  claude-code:
    binary: claude
    support_level: 3
  codex:
    binary: codex
    support_level: 3
  gemini-cli:
    binary: gemini
    support_level: 3
  aider:
    binary: aider
    support_level: 3
  openhands:
    binary: openhands
    support_level: 2
  opencode:
    binary: opencode
    support_level: 2
  goose:
    binary: goose
    support_level: 2
  cline:
    binary: cline
    support_level: 2
  qodo:
    binary: qodo
    support_level: 2
  mistral-vibe:
    binary: vibe
    support_level: 2
    programmatic_flag: "-p"
    output_format: streaming
  hermes:
    binary: ollama
    model: nous-hermes-3
    support_level: 1
  openclaw:
    binary: openclaw
    support_level: 1
    profile_prefix: swarm-

messaging:
  db_path: .swarm/messages.db

worktree:
  base_path: .swarm/worktrees
  one_worktree_per_agent: true
```

---

## 17. Milestone Roadmap

### Phase 1 — Foundation
- [ ] Project scaffolding
- [ ] `AgentRuntime` base interface
- [ ] role registry + role contracts
- [ ] SQLite event/message bus
- [ ] git worktree manager
- [ ] fleet status model

### Phase 2 — Core Roles
- [ ] coordinator
- [ ] scout
- [ ] builder
- [ ] developer
- [ ] tester
- [ ] reviewer
- [ ] merger
- [ ] monitor

### Phase 3 — Runtime Adapters v1
- [ ] Claude Code adapter
- [ ] Codex CLI adapter
- [ ] Gemini CLI adapter
- [ ] Aider adapter
- [ ] OpenHands CLI adapter
- [ ] OpenCode adapter
- [ ] Vibe adapter
- [ ] Hermes adapter

### Phase 4 — Role Safety
- [ ] role contracts
- [ ] tool policy enforcement
- [ ] filesystem policy enforcement
- [ ] structured output validation
- [ ] drift detection
- [ ] supervisor escalation flow

### Phase 5 — TUI
- [ ] overseer chat panel
- [ ] fleet panel
- [ ] selected agent output
- [ ] event log
- [ ] role contract viewer
- [ ] drift/stall warnings
- [ ] nudge / retry / kill actions

### Phase 6 — Extended Adapters
- [ ] Goose adapter
- [ ] Cline CLI adapter
- [ ] Qodo Gen CLI adapter
- [ ] OpenClaw experimental adapter

### Phase 7 — Polish
- [ ] `swarm init`
- [ ] `swarm doctor`
- [ ] replay logs
- [ ] merge queue
- [ ] README
- [ ] demo GIF / asciinema

---

## 18. Key Differences from Overstory

| Feature | Overstory | Swarm |
|---------|-----------|---------------|
| Runtime scope | Focused supported runtime set | Broad coding-agent CLI support |
| Primary UX | CLI + dashboard | Overseer-first orchestration TUI |
| Role model | Strong hierarchy | Strong hierarchy plus strict role locking |
| Developer role | Not central in exposed role list | First-class role |
| Tester role | Validation/review patterns exist | First-class dedicated role |
| Runtime adapters | Pluggable | Pluggable with capability matrix |
| Drift enforcement | Guard-centric | Guard + contract + schema + policy |
| Goal | Swarm orchestration | Swarm orchestration across popular coding agents |

---

## 19. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Runtime fragmentation across many CLIs | Use capability flags and support levels |
| Some tools are interactive-first, not orchestration-first | Wrap them with adapter policies and define partial support honestly |
| Agents drift out of role | Enforce contracts, tool restrictions, structured outputs, and drift detection |
| Reviewer or Scout starts editing code | Block with runtime/tool/filesystem policy |
| Builder tries to self-review or self-merge | Force handoff chain |
| Too many adapters delay shipping | Ship Tier 1 first |
| Overseer context becomes too large | Summarize agent state into compact packets |
| Merge conflicts multiply with concurrency | Use one worktree per agent and a merge queue |
| Local-model runtimes act inconsistently | Mark them Level 1 or Level 2 until stabilized |

---

## 20. Non-Negotiable Rules

- Every agent has exactly **one role** per session.
- Roles are assigned by the coordinator and cannot be self-changed.
- Every task declares the required role.
- Every agent writes structured output for its role.
- Every handoff is explicit.
- Non-implementation agents do not edit code.
- Non-merge agents do not merge.
- Only spawn-capable roles can create child agents.
- Monitor and Supervisor can intervene, but not silently replace role policy.

---

## 21. References

- [Overstory GitHub](https://github.com/jayminwest/overstory)
- [Textual Docs](https://textual.textualize.io/)
- [Typer Docs](https://typer.tiangolo.com/)
- [aiosqlite](https://github.com/omnilib/aiosqlite)
- [libtmux](https://libtmux.git-pull.com/)
- [Pydantic v2](https://docs.pydantic.dev/)
- Overstory README / architecture / agent hierarchy
- Overstory changelog and release notes for role evolution
- `vibe --help`
- `openclaw --help`
- Aider docs
- OpenHands CLI docs
- OpenCode docs
- Goose docs
- Cline CLI docs
- Qodo Gen CLI materials
