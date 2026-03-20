# Swarm Roadmap

## Milestone 1 — Core Orchestration

### Phase 1 — Foundation (Completed)
- [x] Project scaffolding
- [x] AgentRuntime base interface
- [x] Role registry + role contracts
- [x] SQLite event/message bus
- [x] Git worktree manager
- [x] Fleet status model

### Phase 2 — Core Roles (In Progress)
- [x] Scout role definition + contract
- [x] Developer role definition + contract
- [x] Builder role definition + contract
- [x] Tester role definition + contract
- [ ] Orchestrator role definition + contract
- [ ] Coordinator role definition + contract
- [ ] Supervisor role definition + contract
- [ ] Lead role definition + contract
- [ ] Reviewer role definition + contract
- [ ] Merger role definition + contract
- [ ] Monitor role definition + contract

### Phase 3 — Runtime Adapters v1 (Mostly Completed)
- [x] Claude Code adapter
- [x] Codex CLI adapter
- [x] Gemini CLI adapter
- [ ] Aider adapter
- [ ] OpenHands CLI adapter
- [x] OpenCode adapter
- [x] Mistral Vibe adapter
- [x] Hermes adapter
- [x] Echo adapter

### Phase 4 — Role Safety (In Progress)
- [x] Role locking mechanism
- [x] Anti-drift detection system
- [ ] Tool policy enforcement
- [ ] Filesystem access controls
- [ ] Structured output validation
- [ ] Supervisor intervention workflow
- [ ] Drift detection alerts

### Phase 5 — TUI (Mostly Completed)
- [x] Overseer chat panel
- [x] Fleet panel
- [x] Selected agent output
- [x] Event log
- [x] Role contract viewer
- [x] Drift/stall warnings
- [x] Nudge / retry / kill actions

### Phase 6 — Extended Adapters (Not Started)
- [ ] Goose adapter
- [ ] Cline CLI adapter
- [ ] Qodo Gen CLI adapter
- [ ] OpenClaw experimental adapter

### Phase 7 — Polish (Not Started)
- [ ] `swarm init`
- [ ] `swarm doctor`
- [ ] Replay logs
- [ ] Merge queue
- [ ] README
- [ ] Demo GIF / asciinema
