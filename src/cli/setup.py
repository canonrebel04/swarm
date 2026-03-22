"""
swarm setup — interactive model/provider configuration wizard.
Run before TUI or via: swarm setup
"""
import getpass
import os
import sys
import asyncio
from pathlib import Path
import yaml
import aiohttp

# Fallback models in case API fetch fails
FALLBACK_MISTRAL = [
    "mistral-large-latest",
    "mistral-medium-latest",
    "mistral-small-latest",
    "codestral-latest",
    "open-mistral-nemo"
]

FALLBACK_OPENAI = [
    "o3-mini",
    "o1-preview",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo"
]

FALLBACK_OLLAMA = [
    "hermes",
    "llama3",
    "mistral",
    "phi3"
]

# All known provider/model combos across all 8 runtimes
PROVIDER_CATALOG = [
    # (display_label, runtime_key, model_string, env_var_needed)
    ("Anthropic  · claude-opus-4-5      (best quality)",   "claude-code", "claude-opus-4-5",          "ANTHROPIC_API_KEY"),
    ("Anthropic  · claude-sonnet-4-5    (fast + capable)", "claude-code", "claude-sonnet-4-5",         "ANTHROPIC_API_KEY"),
    ("Anthropic  · claude-haiku-3-5     (cheapest)",       "claude-code", "claude-haiku-3-5",          "ANTHROPIC_API_KEY"),
    ("OpenAI     · (fetch dynamic list via API)",          "codex",       "__dynamic__",               "OPENAI_API_KEY"),
    ("Google     · gemini-2.5-pro       (deep analysis)",  "gemini",      "gemini-2.5-pro",            "GOOGLE_API_KEY"),
    ("Google     · gemini-2.5-flash     (fast)",           "gemini",      "gemini-2.5-flash",          "GOOGLE_API_KEY"),
    ("Mistral    · (fetch dynamic list via API)",          "vibe",        "__dynamic__",               "MISTRAL_API_KEY"),
    ("Ollama     · (fetch local models via API)",          "hermes",      "__dynamic__",               None),
    ("Custom     · enter manually...",                     "__custom__",  "",                          None),
]

CONFIG_PATH = Path("config.yaml")


def _read_config() -> dict:
    if CONFIG_PATH.exists():
        return yaml.safe_load(CONFIG_PATH.read_text()) or {}
    return {}


def _write_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False))


def _bold(s: str) -> str:
    return f"\033[1m{s}\033[0m"


def _cyan(s: str) -> str:
    return f"\033[96m{s}\033[0m"


def _green(s: str) -> str:
    return f"\033[92m{s}\033[0m"


def _dim(s: str) -> str:
    return f"\033[2m{s}\033[0m"


def _clear_line() -> None:
    sys.stdout.write("\033[2K\r")
    sys.stdout.flush()


def run_setup() -> None:
    """Full interactive setup wizard — called by `swarm setup`."""
    asyncio.run(_run_setup_async())


async def _run_setup_async() -> None:
    os.system("clear")
    print(_cyan("╔══════════════════════════════════════════════════════╗"))
    print(_cyan("║") + _bold("        🤖  Swarm — Model & Provider Setup          ") + _cyan("║"))
    print(_cyan("╚══════════════════════════════════════════════════════╝"))
    print()

    cfg = _read_config()

    # ── Step 1: Overseer model selection ──────────────────────────────────────
    print(_bold("Step 1/3 — Overseer model"))
    print(_dim("  The overseer is the main LLM that decomposes tasks and"))
    print(_dim("  coordinates agents. Pick the provider/model to use.\n"))

    current_model   = cfg.get("overseer", {}).get("model", "mistral-large-latest")
    current_runtime = cfg.get("overseer", {}).get("runtime", "vibe")
    print(f"  Current: {_cyan(current_runtime)} / {_cyan(current_model)}\n")

    for i, (label, _, _, _) in enumerate(PROVIDER_CATALOG):
        prefix = _green("  ▶") if i == 0 else "   "
        print(f"{prefix} [{i + 1:2}]  {label}")

    print()
    while True:
        try:
            raw = input(_bold("  Select [1-{n}]: ".format(n=len(PROVIDER_CATALOG)))).strip()
            choice = int(raw) - 1
            if 0 <= choice < len(PROVIDER_CATALOG):
                break
        except (ValueError, KeyboardInterrupt):
            print("\n  Aborted.")
            return

    label, runtime_key, model_str, env_var = PROVIDER_CATALOG[choice]

    # ── Handle Dynamic Model List ──────────────────────────────────────────
    if model_str == "__dynamic__":
        print()
        
        # We need the key now to fetch (except for Ollama)
        api_key = None
        if env_var:
            print(_bold(f"  Fetching {runtime_key} model list..."))
            api_key = os.environ.get(env_var) or _read_env_file(env_var)
            if not api_key:
                print(_dim(f"  {env_var} not found. Please provide it to fetch models."))
                api_key = _secure_input(f"  Enter {runtime_key} API Key: ")
                if api_key:
                    _write_env_file(env_var, api_key)
        
        if runtime_key == "vibe":
            models = await _fetch_models_via_api("https://api.mistral.ai", api_key, FALLBACK_MISTRAL)
        elif runtime_key == "codex":
            models = await _fetch_models_via_api("https://api.openai.com", api_key, FALLBACK_OPENAI)
        elif runtime_key == "hermes":
            models = await _fetch_models_via_api("http://localhost:11434", "ollama", FALLBACK_OLLAMA)
        else:
            models = ["default"]

        print(f"  Available models ({len(models)} found):")
        for i, m in enumerate(models):
            print(f"    [{i + 1:2}]  {m}")
        
        while True:
            try:
                raw = input(_bold(f"  Select [1-{len(models)}]: ")).strip()
                m_choice = int(raw) - 1
                if 0 <= m_choice < len(models):
                    model_str = models[m_choice]
                    break
            except (ValueError, KeyboardInterrupt, EOFError):
                print("\n  Aborted.")
                return

    # ── Step 2: API key ────────────────────────────────────────────────────────
    if env_var:
        # Check if we already have it (might have been entered in dynamic step)
        existing = os.environ.get(env_var) or _read_env_file(env_var)
        
        if existing:
            # Skip key entry if we just set it or it exists, unless they want to change
            # But let's show current status
            print()
            print(_bold(f"Step 2/3 — API key for {env_var}"))
            masked = "•" * len(existing)
            print(f"  Current value: {_dim(masked)} (already set)")
            raw_key = _secure_input("  New key (Enter to keep existing): ")
            if raw_key:
                _write_env_file(env_var, raw_key)
                print(_green(f"  ✓ Saved to .env"))
        else:
            print()
            print(_bold(f"Step 2/3 — API key for {env_var}"))
            print(_dim("  No existing key found in environment or .env file."))
            raw_key = _secure_input("  Enter API key: ")
            if raw_key:
                _write_env_file(env_var, raw_key)
                print(_green(f"  ✓ Saved to .env"))
    else:
        print()
        print(_dim("Step 2/3 — API key: not required for this provider, skipping."))

    # ── Step 3: Agent role → runtime mapping (optional) ───────────────────────
    print()
    print(_bold("Step 3/3 — Per-role runtime assignment  ") + _dim("(optional, press Enter to keep defaults)"))
    print(_dim("  Assign which runtime handles each agent role."))
    print(_dim("  Available runtimes: vibe, claude-code, codex, gemini, hermes, opencode, openclaw\n"))

    roles = cfg.get("roles", {}).get("enabled", [
        "scout", "builder", "developer", "tester", "reviewer", "merger", "monitor"
    ])

    role_runtime_map = cfg.get("role_runtimes", {})
    DEFAULTS = {
        "scout":     "codex",
        "reviewer":  "codex",
        "builder":   "hermes",
        "tester":    "hermes",
        "developer": "claude-code",
        "merger":    "gemini",
        "monitor":   "openclaw",
        "coordinator": "vibe",
        "orchestrator": "openclaw",
    }

    new_map = {}
    for role in roles:
        current = role_runtime_map.get(role, DEFAULTS.get(role, "vibe"))
        raw = input(f"  {role:<14} [{_cyan(current)}]: ").strip()
        new_map[role] = raw if raw else current

    # ── Write config ───────────────────────────────────────────────────────────
    if "overseer" not in cfg:
        cfg["overseer"] = {}
    cfg["overseer"]["runtime"] = runtime_key
    cfg["overseer"]["model"]   = model_str
    cfg["role_runtimes"]       = new_map

    # Ensure runtime is present in runtimes block
    if "runtimes" not in cfg:
        cfg["runtimes"] = {}
    if runtime_key not in cfg["runtimes"] and runtime_key != "__custom__":
        cfg["runtimes"][runtime_key] = _default_runtime_block(runtime_key)

    _write_config(cfg)
    print()
    print(_green("╔══════════════════════════════════════════════════════╗"))
    print(_green("║  ✓  Configuration saved to config.yaml               ║"))
    print(_green("╚══════════════════════════════════════════════════════╝"))
    print()
    print(f"  Overseer: {_cyan(runtime_key)} / {_cyan(model_str)}")
    print(f"  Run {_bold('swarm')} to launch.\n")


def _read_env_file(key: str) -> str | None:
    env_file = Path(".env")
    if not env_file.exists():
        return None
    for line in env_file.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _write_env_file(key: str, value: str) -> None:
    env_file = Path(".env")
    if env_file.exists():
        lines = env_file.read_text().splitlines()
    else:
        lines = []
    
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f'{key}="{value}"'
            updated = True
            break
    if not updated:
        lines.append(f'{key}="{value}"')
    env_file.write_text("\n".join(lines) + "\n")


def _secure_input(prompt: str) -> str:
    """Get secure input using getpass with fallback."""
    try:
        return getpass.getpass(prompt).strip()
    except Exception:
        # Fallback to regular input if getpass fails
        print("  ⚠️  Secure input unavailable, falling back to regular input")
        return input(prompt).strip()


async def _fetch_models_via_api(base_url: str, api_key: str | None, fallback: list[str]) -> list[str]:
    if not api_key:
        return fallback
    
    base_url = base_url.rstrip("/")
    url = f"{base_url}/v1/models"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5.0
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = [m["id"] for m in data.get("data", []) if "id" in m]
                    if models:
                        return sorted(models)
    except Exception:
        pass
    return fallback


def _default_runtime_block(runtime_key: str) -> dict:
    defaults = {
        "vibe":        {"binary": "vibe",        "programmatic_flag": "-p",      "output_format": "streaming"},
        "claude-code": {"binary": "claude",       "programmatic_flag": "--print", "output_format": "stream-json"},
        "codex":       {"binary": "codex",        "programmatic_flag": "exec",    "output_format": "json"},
        "gemini":      {"binary": "gemini",       "programmatic_flag": "-p",      "output_format": "stream-json"},
        "hermes":      {"binary": "hermes",       "programmatic_flag": "chat -q", "output_format": "text"},
        "opencode":    {"binary": "opencode",     "programmatic_flag": "run",     "output_format": "stream-json"},
        "openclaw":    {"binary": "openclaw",     "programmatic_flag": "agent",   "output_format": "json"},
    }
    return defaults.get(runtime_key, {"binary": runtime_key, "output_format": "text"})
