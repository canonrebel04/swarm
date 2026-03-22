# Plan 10-3: Docker Containerized Adapter

## Objective
Implement agent execution in ephemeral Docker containers.

## Tasks
1. **Docker SDK**: Implement `DockerRuntime` in `src/runtimes/docker.py`.
2. **Container Management**: Spawn containers with `volumes` mapping for the worktree.
3. **Log Streaming**: Stream container logs to the Swarm event bus.
4. **Image Handling**: Support specifying a custom image per agent role or config.

## Verification
- [ ] Manual test: Spawn a `claude-code` agent in a Docker container and verify file edits propagate back to the local worktree.
- [ ] Verify automatic container removal on finish.
