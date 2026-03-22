# Phase 10 Context: Cloud Deployment (Remote Runtimes)

## Overview
Phase 10 enables Swarm to orchestrate agents running on remote servers (via SSH) or in ephemeral containers (via Docker), allowing for better scaling and environment isolation.

## Implementation Decisions

### Remote Interface
- Define `RemoteAgentRuntime(AgentRuntime)` as a base class for cloud-capable runtimes.
- Requires handling of remote file synchronization or mounting.

### SSH Adapter
- Use `paramiko` for SSH/SCP operations.
- Assume the remote host has the necessary agent binaries (e.g., `vibe`, `claude`) installed.
- Worktrees will be synced to a specific directory on the remote host.

### Docker Adapter
- Use the `docker` Python SDK.
- Spawn a new container for each agent session.
- Mount the local worktree path as a volume in the container.
- Image management: Use a base image with all common agent tools pre-installed.

## Gray Areas
- How to handle real-time streaming over SSH? *Decision: Poll `stdout` or use `paramiko.Channel` for interactive-like streaming.*
- Network latency impacts on TUI? *Decision: Use aggressive async timeouts and background heartbeats.*
