# Research: Phase 6 — Extended Adapters (Goose, Cline, Qodo)

## Goose Adapter
- **Binary:** `goose`
- **Headless Command:** `goose run`
- **Flags:**
    - `-t "..."`: Task description.
    - `--instructions <file>`: Load system instructions (GSD style).
    - `-q`: Quiet mode for cleaner output.
    - `--output-format json`: Structured results.
- **Role Mapping:** Can pass role-specific instruction files.

## Cline Adapter
- **Binary:** `cline`
- **Headless Flags:**
    - `-y` / `--yolo`: Auto-approve and force headless.
    - `--json`: Structured output.
- **Isolation:** Mount worktree path as the base directory.

## Qodo Gen Adapter
- **Binary:** `qodo`
- **Headless Flags:**
    - `--ci`: Continuous integration mode.
    - `-y`: Auto-confirm.
    - `--log <path>`: Capture detailed session logs.
- **Behavior:** Good for focused execution tasks.

## General Strategy
All three runtimes follow the "Task-first" execution style, making them ideal for Builder, Tester, or Scout roles within Swarm.
