# src/runtimes/gemini.py
import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import AsyncIterator

from .base import AgentRuntime, AgentConfig, AgentStatus, RuntimeCapabilities


class GeminiRuntime(AgentRuntime):
    """
    Google Gemini CLI adapter.

    Headless mode: gemini -p "prompt" --output-format stream-json
    
    Confirmed JSONL event types from official geminicli.com docs:
      init         → {"type":"init",    "sessionId":"...", "model":"..."}
      message      → {"type":"message", "role":"assistant"|"user", "content":"..."}
                     OR streaming chunk: {"type":"message", "role":"assistant",
                                          "content":"chunk", "streaming":true}
      tool_use     → {"type":"tool_use", "tool":"run_shell_command",
                                          "args":{...}, "id":"..."}
      tool_result  → {"type":"tool_result", "tool":"...", "id":"...",
                                             "result":{...}, "error":"..."}
      error        → {"type":"error",   "message":"...", "fatal":bool}
      result       → {"type":"result",  "response":"final text",
                                         "stats":{"session":{},"model":{},"tools":{}}}

    Role enforcement:
      1. --approval-mode plan   → read-only mode (Gemini built-in, strongest)
      2. --approval-mode yolo   → auto-approve all (developer/merger/builder)
      3. --policy file.toml     → Policy Engine (deny rules remove tool from model context)
    
    Resume: gemini --resume latest -p "follow-up"
    """

    # Confirmed Gemini CLI tool names (same pattern as Vibe/Codex)
    # Source: gemini-cli default tool registry
    KNOWN_TOOLS = {
        "read_file", "write_file", "edit_file",
        "list_directory", "glob", "grep",
        "run_shell_command",
        "web_search", "web_fetch",
        "read_many_files", "find_files",
    }

    # approval-mode per role
    # "plan" = read-only mode built into Gemini — strongest soft enforcement
    # "auto_edit" = auto-approve file edits only, bash still asks
    # "yolo" = auto-approve everything
    ROLE_APPROVAL: dict[str, str] = {
        "scout":        "plan",       # built-in read-only mode
        "reviewer":     "plan",
        "coordinator":  "plan",
        "supervisor":   "plan",
        "lead":         "plan",
        "monitor":      "plan",
        "builder":      "auto_edit",  # file edits auto, bash manual
        "tester":       "auto_edit",
        "developer":    "yolo",       # full auto for headless
        "merger":       "yolo",
        "orchestrator": "plan",
    }

    # Model per role
    ROLE_MODEL: dict[str, str] = {
        "scout":        "gemini-2.5-flash",
        "reviewer":     "gemini-2.5-pro",   # deep analysis
        "coordinator":  "gemini-2.5-flash",
        "supervisor":   "gemini-2.5-flash",
        "lead":         "gemini-2.5-pro",
        "builder":      "gemini-2.5-flash",
        "tester":       "gemini-2.5-flash",
        "monitor":      "gemini-2.5-flash",
        "developer":    "gemini-2.5-pro",   # complex implementation
        "merger":       "gemini-2.5-flash",
        "orchestrator": "gemini-2.5-pro",
    }

    def __init__(self) -> None:
        self._sessions:    dict[str, asyncio.subprocess.Process] = {}
        self._session_ids: dict[str, str] = {}   # internal_id → gemini sessionId
        self._configs:     dict[str, AgentConfig] = {}
        self._last_output: dict[str, str] = {}
        self._policy_files: dict[str, Path] = {} # temp policy TOML paths
        self._event_callback = None

    # ── Interface ──────────────────────────────────────────────────────────────

    @property
    def runtime_name(self) -> str:
        return "gemini"

    @property
    def capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            interactive_chat=True,
            headless_run=True,
            resume_session=True,
            streaming_output=True,
            tool_allowlist=True,   # via Policy Engine
            sandbox_support=False, # --sandbox flag exists but is boolean only
            agent_profiles=False,
            parallel_safe=True,
        )

    # ── Spawn ──────────────────────────────────────────────────────────────────

    async def spawn(self, config: AgentConfig) -> str:
        approval  = self.ROLE_APPROVAL.get(config.role, "auto_edit")
        model     = config.model or self.ROLE_MODEL.get(config.role, "gemini-2.5-flash")
        policy_path = self._write_policy_file(config)
        full_prompt = self._build_full_prompt(config)

        cmd = [
            "gemini",
            "--prompt",   full_prompt,
            "--output-format", "stream-json",
            "--model",    model,
            "--approval-mode", approval,
            "--include-directories", config.worktree_path,
        ]

        # Attach policy file if one was generated for this role
        if policy_path:
            cmd += ["--policy", str(policy_path)]
            self._policy_files[f"gemini-{config.name}"] = policy_path

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=config.worktree_path,
            env={**os.environ, **(config.extra_env or {})},
        )

        session_id = f"gemini-{config.name}-{proc.pid}"
        self._sessions[session_id]    = proc
        self._configs[session_id]     = config
        self._last_output[session_id] = ""

        if self._event_callback:
            self._event_callback(
                "spawn", config.name,
                f"spawned as {config.role} via gemini ({approval} mode, {model})"
            )

        return session_id

    # ── Nudge / resume ─────────────────────────────────────────────────────────

    async def send_message(self, session_id: str, message: str) -> None:
        config = self._configs.get(session_id)
        if not config:
            return

        approval = self.ROLE_APPROVAL.get(config.role, "auto_edit")
        model    = config.model or self.ROLE_MODEL.get(config.role, "gemini-2.5-flash")

        cmd = [
            "gemini",
            "--resume", "latest",           # resume most recent session
            "--prompt", message,
            "--output-format", "stream-json",
            "--approval-mode", approval,
            "--include-directories", config.worktree_path,
        ]

        # Re-attach policy file on resume
        key = f"gemini-{config.name}"
        if key in self._policy_files:
            cmd += ["--policy", str(self._policy_files[key])]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=config.worktree_path,
            env={**os.environ, **(config.extra_env or {})},
        )
        self._sessions[session_id] = proc

    # ── Stream output ──────────────────────────────────────────────────────────

    async def stream_output(self, session_id: str) -> AsyncIterator[str]:
        proc = self._sessions.get(session_id)
        if not proc or not proc.stdout:
            return

        async for raw in proc.stdout:
            line = raw.decode(errors="replace").strip()
            if not line:
                continue
            text = self._parse_stream_event(session_id, line)
            if text:
                self._last_output[session_id] = text
                yield text

    # ── Status ─────────────────────────────────────────────────────────────────

    async def get_status(self, session_id: str) -> AgentStatus:
        proc   = self._sessions.get(session_id)
        config = self._configs.get(session_id)

        if not proc:
            state = "error"
        elif proc.returncode is None:
            state = "running"
        elif proc.returncode == 0:
            state = "done"
        else:
            state = "error"

        return AgentStatus(
            name=config.name if config else session_id,
            role=config.role if config else "unknown",
            state=state,
            current_task=config.task if config else "",
            runtime=self.runtime_name,
            last_output=self._last_output.get(session_id, ""),
            pid=proc.pid if proc else None,
        )

    # ── Kill ───────────────────────────────────────────────────────────────────

    async def kill(self, session_id: str) -> None:
        proc = self._sessions.pop(session_id, None)
        config = self._configs.pop(session_id, None)
        self._session_ids.pop(session_id, None)
        self._last_output.pop(session_id, None)

        # Clean up temp policy file
        if config:
            key = f"gemini-{config.name}"
            pf = self._policy_files.pop(key, None)
            if pf and pf.exists():
                pf.unlink()

        if proc and proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()

    # ── Private helpers ────────────────────────────────────────────────────────

    def _build_full_prompt(self, config: AgentConfig) -> str:
        base = ""
        p = Path(config.system_prompt_path)
        if p.exists():
            base = p.read_text().strip() + "\n\n"

        behavioral = self._role_behavioral_constraints(config.role)
        completion = (
            f"\nWhen your task is complete, output this JSON on its own line:\n"
            f'{{"role":"{config.role}","status":"done",'
            f'"summary":"...","files_changed":[],"handoff_to":"..."}}\n'
        )

        return (
            f"{base}"
            f"ROLE CONTRACT:\n"
            f"You are {config.name}, a {config.role} agent.\n"
            f"{behavioral}"
            f"{completion}"
            f"\n---\n\nTASK:\n{config.task}"
        )

    def _role_behavioral_constraints(self, role: str) -> str:
        constraints = {
            "scout": (
                "You MUST NOT edit, write, or delete any files.\n"
                "You are in plan mode — write tools are blocked by the CLI.\n"
            ),
            "reviewer": (
                "You MUST NOT edit, write, or delete any files.\n"
                "Produce a written review only.\n"
            ),
            "builder": (
                "You MAY edit files and run build/test commands.\n"
                "You MUST NOT push to remote or merge branches.\n"
            ),
            "tester": (
                "You MAY write test files and run pytest/test commands.\n"
                "You MUST NOT commit or push changes.\n"
            ),
            "developer": (
                "You MAY implement features and write code.\n"
                "You MUST NOT push without reviewer approval.\n"
            ),
            "merger": (
                "You handle merge operations only.\n"
                "You MUST NOT write new feature code.\n"
            ),
            "monitor": (
                "You MUST NOT edit or write any files.\n"
                "You MAY run read-only inspection commands only.\n"
            ),
        }
        return constraints.get(role, "")

    def _write_policy_file(self, config: AgentConfig) -> Path | None:
        """
        Generate a TOML policy file for roles that need tool-level deny rules.
        
        Gemini Policy Engine: deny rules completely remove the tool from the
        model's context window — the model never sees it as an option.
        This is stronger than just blocking execution.
        
        Only generate for roles where prompt + approval-mode isn't enough.
        scout/reviewer use --approval-mode plan (built-in read-only) — no policy needed.
        builder/tester need bash but not git push — policy enforces the distinction.
        """
        policy_rules = self._get_policy_rules(config.role)
        if not policy_rules:
            return None

        toml_content = f'# Auto-generated policy for role: {config.role}\n\n'
        toml_content += policy_rules

        # Write to temp file — cleaned up on kill()
        tmp = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".toml",
            prefix=f"polyglot_{config.role}_",
            delete=False,
        )
        tmp.write(toml_content)
        tmp.close()
        return Path(tmp.name)

    def _get_policy_rules(self, role: str) -> str:
        """
        TOML policy rules per role using Gemini Policy Engine syntax.
        deny rules remove the tool from model context entirely.
        allow rules auto-execute without confirmation.
        """
        policies = {

            # builder: allow file ops + safe git, deny push/merge
            "builder": '''
[[rule]]
name = "allow_file_ops"
description = "Auto-allow file read/write operations"
effect = "allow"
tool_name = "write_file"
priority = 100

[[rule]]
name = "allow_edit"
effect = "allow"
tool_name = "edit_file"
priority = 100

[[rule]]
name = "allow_shell_safe"
effect = "allow"
tool_name = "run_shell_command"
args_pattern = "^(pytest|python|pip|git add|git status|git diff|git log)"
priority = 90

[[rule]]
name = "deny_git_push"
description = "Builders cannot push to remote"
effect = "deny"
tool_name = "run_shell_command"
args_pattern = "git push|git merge|git rebase"
priority = 200
''',

            # tester: allow test commands, deny all git write ops
            "tester": '''
[[rule]]
name = "allow_test_commands"
effect = "allow"
tool_name = "run_shell_command"
args_pattern = "^(pytest|python -m pytest|coverage|python -m coverage)"
priority = 100

[[rule]]
name = "allow_write_tests"
effect = "allow"
tool_name = "write_file"
priority = 100

[[rule]]
name = "deny_git_write"
effect = "deny"
tool_name = "run_shell_command"
args_pattern = "git (push|merge|commit|rebase|reset|checkout -b)"
priority = 200
''',

            # developer: allow everything except push (reviewer must sign off)
            "developer": '''
[[rule]]
name = "deny_git_push"
description = "Developers cannot push without reviewer sign-off"
effect = "deny"
tool_name = "run_shell_command"
args_pattern = "git push"
priority = 200
''',

            # monitor: deny all write tools at model context level
            "monitor": '''
[[rule]]
name = "deny_write_file"
effect = "deny"
tool_name = "write_file"
priority = 200

[[rule]]
name = "deny_edit_file"
effect = "deny"
tool_name = "edit_file"
priority = 200

[[rule]]
name = "deny_shell_writes"
effect = "deny"
tool_name = "run_shell_command"
args_pattern = "git (push|merge|commit|add)|rm |mv |cp "
priority = 200
''',
            # scout/reviewer use --approval-mode plan — no policy file needed
            # merger gets full access — no restrictions
        }
        return policies.get(role, "")

    def _parse_stream_event(self, session_id: str, line: str) -> str | None:
        """
        Parse confirmed Gemini CLI --output-format stream-json JSONL events.

        Confirmed event types from official geminicli.com/docs/cli/headless:
          init        → session metadata, capture sessionId
          message     → assistant content (streaming chunks + final)
          tool_use    → tool call with args
          tool_result → tool output
          error       → non-fatal warnings + fatal errors
          result      → final response + stats
        """
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            return line if line else None

        event_type = obj.get("type", "")

        # ── Init — capture session ID for resume ───────────────────────────────
        if event_type == "init":
            sid = obj.get("sessionId") or obj.get("session_id")
            if sid:
                self._session_ids[session_id] = sid
            model = obj.get("model", "")
            return f"[init] session started ({model})" if model else None

        # ── Message — primary output ───────────────────────────────────────────
        if event_type == "message":
            role    = obj.get("role", "")
            content = obj.get("content", "")
            is_chunk = obj.get("streaming", False)

            if role != "assistant" or not content:
                return None

            # Streaming chunks — pass through directly for live display
            # Final message (streaming=False or absent) — same treatment
            return content if isinstance(content, str) else None

        # ── Tool use ───────────────────────────────────────────────────────────
        if event_type == "tool_use":
            tool = obj.get("tool", "unknown")
            args = obj.get("args", {})

            if tool == "run_shell_command":
                cmd = args.get("command", "")[:100]
                return f"[shell] $ {cmd}"
            elif tool == "write_file":
                return f"[write] {args.get('path', '')}"
            elif tool == "edit_file":
                return f"[edit] {args.get('path', '')}"
            elif tool == "read_file":
                return f"[read] {args.get('path', '')}"
            elif tool == "read_many_files":
                paths = args.get("paths", [])
                return f"[read] {', '.join(str(p) for p in paths[:3])}"
            elif tool == "list_directory":
                return f"[ls] {args.get('path', '.')}"
            elif tool in ("glob", "find_files"):
                return f"[glob] {args.get('pattern', '')}"
            elif tool == "grep":
                return f"[grep] {args.get('pattern', '')} in {args.get('path', '.')}"
            elif tool == "web_search":
                return f"[search] {args.get('query', '')}"
            elif tool == "web_fetch":
                return f"[fetch] {args.get('url', '')}"
            else:
                return f"[{tool}] {str(args)[:80]}"

        # ── Tool result ────────────────────────────────────────────────────────
        if event_type == "tool_result":
            result = obj.get("result", {})
            error  = obj.get("error")

            if error:
                return f"[tool_error] {str(error)[:120]}"

            # Result is usually a dict with output/content key
            if isinstance(result, dict):
                output = result.get("output") or result.get("content") or result.get("text", "")
                if output:
                    lines = str(output).splitlines()[:10]
                    return f"[result] {chr(10).join(lines)}"
            if isinstance(result, str) and result:
                return f"[result] {result[:200]}"

            return None

        # ── Error ──────────────────────────────────────────────────────────────
        if event_type == "error":
            msg   = obj.get("message", "unknown error")
            fatal = obj.get("fatal", False)
            prefix = "[fatal]" if fatal else "[error]"
            return f"{prefix} {msg}"

        # ── Result — final summary ─────────────────────────────────────────────
        if event_type == "result":
            response = obj.get("response", "")
            stats    = obj.get("stats", {})
            model_stats = stats.get("model", {})
            turns = model_stats.get("turns", "?")
            tools_stats = stats.get("tools", {})
            calls = tools_stats.get("calls", "?")
            # Surface final response if it wasn't already streamed
            summary = f"[done] {turns} turns, {calls} tool calls"
            if response and len(response) < 200:
                return f"{response}\n{summary}"
            return summary

        return None
