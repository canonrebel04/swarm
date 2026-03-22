# Plan 10-2: SSH Remote Adapter

## Objective
Implement agent execution on remote servers via SSH.

## Tasks
1. **Paramiko Integration**: Implement `SSHRuntime` in `src/runtimes/ssh.py`.
2. **Execution**: Use `exec_command` to run agent binaries on the remote host.
3. **Streaming**: Capture remote `stdout` and yield locally.
4. **Cleanup**: Ensure remote processes are killed when the session ends.

## Verification
- [ ] Manual test: Spawn a `vibe` agent on a remote host via SSH and receive output in Swarm TUI.
- [ ] Verify worktree syncing before execution.
