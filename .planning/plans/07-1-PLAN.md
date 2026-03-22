# Plan 07-1: CLI Polish & Diagnostics

## Objective
Finalize the Swarm CLI by refining `init`, `doctor`, `roles`, `runtimes`, and adding a `logs` command for auditability.

## Tasks
1. **Refine `init`**:
    - Ensure `.polyglot/` and `.swarm/` directories are created.
    - Template a default `config.yaml` if missing.
2. **Refine `doctor`**:
    - Check for required binaries (claude, vibe, gemini, etc.).
    - Check for required environment variables (API keys).
    - Validate SQLite database connectivity.
3. **Refine `runtimes` & `roles`**:
    - Use `Rich` tables for prettier output.
    - Show status (ready/missing) for runtimes.
4. **Implement `logs`**:
    - Add command to dump the last N events/messages from SQLite.
    - Support `--tail` mode for live log watching.

## Verification
- [ ] `swarm doctor` accurately reports system health.
- [ ] `swarm init` sets up a fresh project correctly.
- [ ] `swarm logs` displays recent agent activity.
