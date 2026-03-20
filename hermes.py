# src/runtimes/hermes.py
import asyncio
import json
import os
from pathlib import Path
from typing import AsyncIterator

from .base import AgentRuntime, AgentConfig, AgentStatus, RuntimeCapabilities


class HermesRuntime(AgentRuntime):
    """
    NousResearch Hermes Agent adapter.

    Headless mode: hermes chat -q "prompt" --quiet
    Key features:
      - --worktree flag: Hermes handles git worktree isolation itself (unique!)
      - --toolsets: group-based tool restriction (web, terminal, skills, files, etc.)
      - --skills: preload specific skills per session
      - --yolo: bypass all approval prompts for headless agents
      - --resume SESSION / --continue: session continuity

    Tool enforcement:
      - --toolsets restricts to named tool groups (coarser than individual tools)
      - hermes tools --summary shows per-platform enabled tools
      - No per-tool allowlist — use toolset groups + prompt constraints

    Output:
      hermes chat --quiet -q "..." suppresses UI chrome, outputs raw response text
      No structured JSONL — plain text stdout (unlike Codex/Gemini/Claude)
      Parse for handoff JSON in final lines of output

    Sessions:
      hermes --continue [NAME]   → resume most recent or named session
      hermes --resume SESSION_ID → resume specific session by ID
      --pass-session-id          → inject session ID into system prompt (useful for tracking)
    """

    # Hermes toolset groups (confirmed from CLI docs)
    # These are named groups, not individual tool names
    # --toolsets accepts comma-separated group names
    TOOLSET_ALL = ["web", "terminal", "skills", "files", "memory", "github"]

    # Toolset policy per role — restrict to safe subsets
    # scout/reviewer: files + memory only (no terminal, no web writes)
    # builder/developer: full access
    ROLE_TOOLSETS: dict[str, list[str]] = {
        "scout":        ["files", "memory"],
        "reviewer":     ["files", "memory"],
        "coordinator":  ["files", "memory"],
        "supervisor":   ["files", "memory"],
        "lead":         ["files", "memory", "web"],
        "monitor":      ["files", "memory"],
        "builder":      ["files", "terminal", "skills", "memory"],
        "tester":       ["files", "terminal", "skills", "memory"],
        "developer":    ["files", "terminal", "skills", "memory", "web", "github"],
        "merger":       ["files", "terminal", "github"],
        "orchestrator": ["files", "memory", "skills"],
    }

    # Skills to preload per role — hermes --skills flag
    # Skills extend the agent with domain-specific capabilities
    ROLE_SKILLS: dict[str, list[str]] = {
        "scout":     [],
        "reviewer":  [],
        "builder":   [],
        "tester":    [],
        "developer": [],
        "merger":    ["github-auth"],   # merger needs git/github access
        "monitor":   [],
        "orchestrator": [],
    }

    # Whether to use --worktree flag — Hermes manages git worktree itself
    # Only disable for roles that need to see the full repo state
    ROLE_USE_WORKTREE: dict[str, bool] = {
        "scout":        True,   # isolated read — safe
        "reviewer":     True,   # isolated read — safe
        "coordinator":  False,  # needs full repo view
        "supervisor":   False,
        "lead":         False,
        "monitor":      False,  # monitors full repo state
        "builder":      True,   # isolated write branch
        "tester":       True,   # isolated test branch
        "developer":    True,   # isolated feature branch
        "merger":       False,  # needs access to multiple branches
        "orchestrator": False,
    }

    def __init__(self) -> None:
        self._sessions:    dict[str, asyncio.subprocess.Process] = {}
        self._session_ids: dict[str, str] = {}   # internal_id → hermes SESSION_ID
        self._configs:     dict[str, AgentConfig] = {}
        self._last_output: dict[str, str] = {}
        self._event_callback = None

    # ── Interface ──────────────────────────────────────────────────────────────

    @property
    def runtime_name(self) -> str:
        return "hermes"

    @property
    def capabilities(self) -> RuntimeCapabilities:
        return RuntimeCapabilities(
            interactive_chat=True,
            headless_run=True,
            resume_session=True,
            streaming_output=True,
            tool_allowlist=True,    # via --toolsets group restriction
            sandbox_support=False,
            agent_profiles=False,
            parallel_safe=True,
        )

    # ── Spawn ──────────────────────────────────────────────────────────────────

    async def spawn(self, config: AgentConfig) -> str:
        full_prompt   = self._build_full_prompt(config)
        toolsets      = self.ROLE_TOOLSETS.get(config.role, ["files", "terminal"])
        skills        = self.ROLE_SKILLS.get(config.role, [])
        use_worktree  = self.ROLE_USE_WORKTREE.get(config.role, True)

        cmd = [
            "hermes", "chat",
            "--quiet",                     # suppress TUI chrome, clean stdout
            "-q", full_prompt,             # single-query headless mode
            "--toolsets", ",".join(toolsets),
            "--yolo",                      # auto-approve all prompts (headless)
            "--pass-session-id",           # inject session ID for tracking
        ]

        # Hermes natively handles git worktree isolation — unique feature
        if use_worktree:
            cmd.append("--worktree")

        # Preload role-specific skills
        for skill in skills:
            cmd += ["--skills", skill]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=config.worktree_path,
            env={**os.environ, **(config.extra_env or {})},
        )

        session_id = f"hermes-{config.name}-{proc.pid}"
        self._sessions[session_id]    = proc
        self._configs[session_id]     = config
        self._last_output[session_id] = ""

        if self._event_callback:
            self._event_callback(
                "spawn", config.name,
                f"spawned as {config.role} via hermes "
                f"(toolsets: {','.join(toolsets)}"
                f"{', worktree' if use_worktree else ''})"
            )

        return session_id

    # ── Nudge / resume ─────────────────────────────────────────────────────────

    async def send_message(self, session_id: str, message: str) -> None:
        config = self._configs.get(session_id)
        if not config:
            return

        toolsets     = self.ROLE_TOOLSETS.get(config.role, ["files", "terminal"])
        skills       = self.ROLE_SKILLS.get(config.role, [])
        hermes_sid   = self._session_ids.get(session_id)
        use_worktree = self.ROLE_USE_WORKTREE.get(config.role, True)

        cmd = [
            "hermes", "chat",
            "--quiet",
            "-q", message,
            "--toolsets", ",".join(toolsets),
            "--yolo",
        ]

        # Resume by session ID if we have it, otherwise --continue
        if hermes_sid:
            cmd += ["--resume", hermes_sid]
        else:
            cmd += ["--continue"]

        if use_worktree:
            cmd.append("--worktree")

        for skill in skills:
            cmd += ["--skills", skill]

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
            text = self._parse_output_line(session_id, line)
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
        self._configs.pop(session_id, None)
        self._session_ids.pop(session_id, None)
        self._last_output.pop(session_id, None)
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
            f"\nWhen your task is complete, output this JSON on its own line "
            f"(last line of your response, no other text after it):\n"
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
                "You MUST NOT run terminal commands that modify state.\n"
                "You MAY only read files, search, and explore.\n"
            ),
            "reviewer": (
                "You MUST NOT edit, write, or delete any files.\n"
                "Produce a written review only. No code changes.\n"
            ),
            "builder": (
                "You MAY edit files and run build/test commands.\n"
                "You MUST NOT push to remote or merge branches.\n"
            ),
            "tester": (
                "You MAY write test files and run test commands.\n"
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

    def _parse_output_line(self, session_id: str, line: str) -> str | None:
        """
        Hermes --quiet -q outputs plain text, not JSONL.
        Two things to extract:
          1. Session ID injected via --pass-session-id
             Format: first line often contains "Session: <id>" or similar
          2. Handoff JSON on the final line(s):
             {"role":"...","status":"done","summary":"...","files_changed":[],"handoff_to":"..."}
          3. Tool activity lines (Hermes prefixes tool output even in quiet mode):
             [tool:bash] $ pytest tests/
             [tool:read] src/main.py
             [tool:write] src/feature.py
        """

        # ── Try to extract session ID from first lines ─────────────────────────
        # --pass-session-id injects it into system prompt context
        # Hermes may echo it in early output as: "Session ID: abc123..."
        if "Session ID:" in line or "session_id:" in line.lower():
            parts = line.split(":", 1)
            if len(parts) == 2:
                sid = parts[1].strip().split()[0]  # take first token after colon
                if sid and session_id not in self._session_ids:
                    self._session_ids[session_id] = sid
            return None   # internal, don't surface

        # ── Tool activity lines ────────────────────────────────────────────────
        # Hermes quiet mode still prefixes tool calls with [tool:name]
        if line.startswith("[tool:"):
            # Already formatted cleanly — pass through as-is
            return line

        # ── Handoff JSON detection ─────────────────────────────────────────────
        if line.startswith("{") and '"status"' in line and '"role"' in line:
            try:
                obj = json.loads(line)
                if obj.get("status") == "done":
                    summary = obj.get("summary", "")
                    handoff = obj.get("handoff_to", "")
                    files   = obj.get("files_changed", [])
                    parts = [f"[done] {summary}"]
                    if files:
                        parts.append(f"[files] {', '.join(files[:5])}")
                    if handoff:
                        parts.append(f"[handoff→] {handoff}")
                    return "\n".join(parts)
            except json.JSONDecodeError:
                pass

        # ── Plain text response ────────────────────────────────────────────────
        # Filter out common Hermes UI chrome that leaks through --quiet
        noise_prefixes = (
            "Hermes Agent",
            "Model:",
            "Provider:",
            "╭", "╰", "│",   # box-drawing characters
            "Using worktree:",
            "Worktree path:",
        )
        if any(line.startswith(p) for p in noise_prefixes):
            return None

        return line if line else None
