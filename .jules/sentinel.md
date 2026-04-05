## 2025-02-28 - Hardcoded API Key and Fail-Open Configuration
**Vulnerability:** The API server had a hardcoded `swarm_dev_key` fallback, allowing unauthorized access if the environment variable was missing. The frontend also hardcoded this key, leaking it to the client side.
**Learning:** Hardcoding credentials in fallback parameters circumvents environment-based security entirely, resulting in a fail-open posture when configuration issues occur. Similarly, putting static keys in client-side code completely invalidates their utility.
**Prevention:** Always implement a fail-closed architecture—if a required security token is missing from the environment, the server should fail to start or reject all requests with a 500 error. Keys should be dynamically requested and stored securely on the client side (e.g., in `localStorage`) rather than embedded in code.

## 2024-04-05 - Fix Command Injection Vulnerability in SSH Runtime

**Vulnerability:** A critical command injection vulnerability existed in `src/runtimes/ssh.py` within the `SSHRuntime.spawn()` method. The variables `config.task` and `remote_path` were concatenated directly into an f-string and passed directly to `paramiko.SSHClient.exec_command` as a shell command without sanitization. An attacker controlling the `config.task` or `config.remote_path` could inject arbitrary shell commands that would be executed on the remote host (e.g., `echo 'hello'; rm -rf /`).

**Learning:** The vulnerability existed because user-controlled strings (like the agent's task description) were directly formatted into shell strings (`f"cd {remote_path} && vibe -p '{config.task}'"`). When executing commands in a shell environment, any special characters (like quotes, semicolons, pipes) are interpreted by the shell, bypassing intended application logic.

**Prevention:** Always use `shlex.quote()` when dynamically inserting variable strings into shell commands. This function wraps strings in single quotes and safely escapes embedded single quotes, ensuring the shell treats the value strictly as a single string literal argument, not as executable syntax. Better yet, when possible, pass command arguments as an array instead of string concatenation, although with SSH `exec_command` string formats are required.
