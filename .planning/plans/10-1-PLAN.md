# Plan 10-1: Remote Runtime Interface

## Objective
Define the abstraction for runtimes that operate outside the local host.

## Tasks
1. **Base Class**: Create `src/runtimes/remote_base.py` with `RemoteAgentRuntime(AgentRuntime)`.
2. **Sync logic**: Define `sync_worktree(local_path, remote_path)` interface.
3. **Config Update**: Add `remote_host`, `remote_user`, and `container_image` to `AgentConfig`.
4. **Registry Integration**: Allow runtimes to be flagged as "remote-capable".

## Verification
- [ ] `RemoteAgentRuntime` correctly inherits and extends the base interface.
- [ ] `AgentConfig` supports remote fields.
