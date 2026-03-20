In the meantime here's the full design spec so you know exactly what's coming:

Two-Part Implementation
Part 1 — swarm setup CLI command (like hermes setup)
Runs before the TUI, detects available runtimes, lets you pick providers and enter API keys:

text
┌─────────────────────────────────────────────┐
│  🤖 Swarm Setup — Model Configuration       │
├─────────────────────────────────────────────┤
│  Orchestrator model:                        │
│  ▶ [anthropic/claude-opus-4-5         ]     │
│    [openai/o3                         ]     │
│    [google/gemini-2.5-pro             ]     │
│    [mistral/mistral-large             ]     │
│    [custom...                         ]     │
├─────────────────────────────────────────────┤
│  API Keys (leave blank to keep existing):   │
│  ANTHROPIC_API_KEY: [***************  ]     │
│  OPENAI_API_KEY:    [               ]       │
│  GOOGLE_API_KEY:    [               ]       │
│  Custom endpoint:   [               ]       │
└─────────────────────────────────────────────┘
Part 2 — In-TUI model selector panel + autofocus fix
A ModelSelectorModal triggered by M keybind or a settings gear icon, plus on_mount autofocus on the overseer chat input — which is a one-liner in Textual:

python
# In SwarmApp.on_mount():
self.query_one(OverseerChatPanel).query_one(Input).focus()
Once you paste the file list and config, I'll write the complete implementation for both parts fitted to your exact class names and theme.


Perfect. I have everything I need. Here's the complete implementation:

```python
# src/cli/setup.py
"""
swarm setup — interactive model/provider configuration wizard.
Run before TUI or via: swarm setup
"""
import os
import sys
from pathlib import Path
import yaml

# All known provider/model combos across all 8 runtimes
PROVIDER_CATALOG = [
    # (display_label, runtime_key, model_string, env_var_needed)
    ("Anthropic  · claude-opus-4-5      (best quality)",   "claude-code", "claude-opus-4-5",          "ANTHROPIC_API_KEY"),
    ("Anthropic  · claude-sonnet-4-5    (fast + capable)", "claude-code", "claude-sonnet-4-5",         "ANTHROPIC_API_KEY"),
    ("Anthropic  · claude-haiku-3-5     (cheapest)",       "claude-code", "claude-haiku-3-5",          "ANTHROPIC_API_KEY"),
    ("OpenAI     · o3                   (best reasoning)", "codex",       "o3",                        "OPENAI_API_KEY"),
    ("OpenAI     · o4-mini              (fast reasoning)", "codex",       "o4-mini",                   "OPENAI_API_KEY"),
    ("Google     · gemini-2.5-pro       (deep analysis)",  "gemini",      "gemini-2.5-pro",            "GOOGLE_API_KEY"),
    ("Google     · gemini-2.5-flash     (fast)",           "gemini",      "gemini-2.5-flash",          "GOOGLE_API_KEY"),
    ("Mistral    · mistral-large-latest (default)",        "vibe",        "mistral-large-latest",      "MISTRAL_API_KEY"),
    ("Mistral    · codestral-latest     (code-focused)",   "vibe",        "codestral-latest",          "MISTRAL_API_KEY"),
    ("Nous       · hermes (local/any)",                    "hermes",      "hermes",                    None),
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

    if runtime_key == "__custom__":
        print()
        runtime_key = input(_bold("  Runtime key (e.g. vibe, codex, gemini): ")).strip()
        model_str   = input(_bold("  Model string (e.g. provider/model-name):  ")).strip()
        env_var     = input(_bold("  Env var for API key (leave blank if none): ")).strip() or None

    # ── Step 2: API key ────────────────────────────────────────────────────────
    if env_var:
        print()
        print(_bold(f"Step 2/3 — API key for {env_var}"))
        existing = os.environ.get(env_var) or _read_env_file(env_var)
        if existing:
            masked = existing[:6] + "***" + existing[-3:]
            print(f"  Current value: {_dim(masked)}")
            raw_key = input(_bold("  New key (Enter to keep existing): ")).strip()
        else:
            print(_dim("  No existing key found in environment or .env file."))
            raw_key = input(_bold("  Enter API key: ")).strip()

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
    lines = env_file.read_text().splitlines() if env_file.exists() else []
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f'{key}="{value}"'
            updated = True
            break
    if not updated:
        lines.append(f'{key}="{value}"')
    env_file.write_text("\n".join(lines) + "\n")


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
```

```python
# src/tui/screens/model_selector.py
"""
In-TUI model selector modal — triggered by pressing 'M' from main screen.
Shows provider list with arrow-key navigation, live search filter,
and custom entry fields. Writes directly to config.yaml on confirm.
"""
from __future__ import annotations
from pathlib import Path
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import (
    Static, ListView, ListItem, Label,
    Input, Button, Rule
)
from textual.containers import Vertical, Horizontal, Container
from textual.binding import Binding
from textual.reactive import reactive
import yaml

PROVIDER_OPTIONS = [
    ("claude-code", "claude-opus-4-5",       "Anthropic",  "claude-opus-4-5        — best quality"),
    ("claude-code", "claude-sonnet-4-5",     "Anthropic",  "claude-sonnet-4-5      — fast + capable"),
    ("claude-code", "claude-haiku-3-5",      "Anthropic",  "claude-haiku-3-5       — cheapest"),
    ("codex",       "o3",                    "OpenAI",     "o3                     — best reasoning"),
    ("codex",       "o4-mini",               "OpenAI",     "o4-mini                — fast reasoning"),
    ("gemini",      "gemini-2.5-pro",        "Google",     "gemini-2.5-pro         — deep analysis"),
    ("gemini",      "gemini-2.5-flash",      "Google",     "gemini-2.5-flash       — fast"),
    ("vibe",        "mistral-large-latest",  "Mistral",    "mistral-large-latest   — default"),
    ("vibe",        "codestral-latest",      "Mistral",    "codestral-latest       — code-focused"),
    ("hermes",      "hermes",                "Nous",       "hermes                 — local/any"),
]

CONFIG_PATH = Path("config.yaml")


class ModelSelectorModal(ModalScreen):
    """Full-screen modal for selecting overseer model and provider."""

    BINDINGS = [
        Binding("escape",     "dismiss(None)", "Cancel",  show=True),
        Binding("ctrl+s",     "save",          "Save",    show=True),
        Binding("enter",      "select_item",   "Select",  show=False),
    ]

    CSS = """
    ModelSelectorModal {
        align: center middle;
    }

    #modal-container {
        width: 72;
        height: auto;
        max-height: 85vh;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }

    #modal-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        padding-bottom: 1;
    }

    #search-input {
        margin-bottom: 1;
    }

    #provider-list {
        height: 14;
        border: solid $primary-darken-2;
    }

    #provider-list > ListItem {
        padding: 0 1;
    }

    #provider-list > ListItem.--highlight {
        background: $accent 20%;
        color: $text;
    }

    #divider {
        margin: 1 0;
    }

    #custom-section Label {
        color: $text-muted;
        margin-bottom: 0;
    }

    #custom-runtime, #custom-model {
        margin-bottom: 1;
    }

    #current-label {
        color: $text-muted;
        text-align: center;
        padding: 1 0 0 0;
    }

    #button-row {
        align: right middle;
        height: 3;
        margin-top: 1;
    }

    #btn-cancel {
        margin-right: 1;
    }

    #btn-save {
        background: $accent;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._cfg = self._load_config()
        self._filtered = list(PROVIDER_OPTIONS)
        self._custom_mode = False

    def _load_config(self) -> dict:
        if CONFIG_PATH.exists():
            return yaml.safe_load(CONFIG_PATH.read_text()) or {}
        return {}

    def compose(self) -> ComposeResult:
        current_rt    = self._cfg.get("overseer", {}).get("runtime", "vibe")
        current_model = self._cfg.get("overseer", {}).get("model", "mistral-large-latest")

        with Vertical(id="modal-container"):
            yield Static("⚙  Overseer Model Selector", id="modal-title")
            yield Static(
                f"Current: [{current_rt}] {current_model}",
                id="current-label"
            )
            yield Rule(id="divider")

            # Search/filter box
            yield Input(
                placeholder="Filter providers... (type to search)",
                id="search-input",
            )

            # Provider list
            lv = ListView(id="provider-list")
            yield lv

            yield Rule()

            # Custom entry (shown when "custom" selected or typed)
            with Vertical(id="custom-section"):
                yield Label("Custom runtime key:")
                yield Input(placeholder="e.g.  vibe  /  codex  /  gemini", id="custom-runtime")
                yield Label("Custom model string:")
                yield Input(placeholder="e.g.  provider/model-name",        id="custom-model")

            with Horizontal(id="button-row"):
                yield Button("Cancel",     id="btn-cancel",  variant="default")
                yield Button("Save  ⌃S",  id="btn-save",    variant="primary")

    def on_mount(self) -> None:
        self._populate_list()
        # Pre-select the currently configured option
        self.query_one("#search-input", Input).focus()

    def _populate_list(self, filter_text: str = "") -> None:
        lv = self.query_one("#provider-list", ListView)
        lv.clear()

        q = filter_text.lower()
        self._filtered = [
            opt for opt in PROVIDER_OPTIONS
            if q in opt[1].lower() or q in opt[2].lower() or q in opt[3].lower()
        ] + ([("__custom__", "", "", "✏  Custom — enter below...")] if not q or "custom" in q else [])

        for runtime, model, provider, label in self._filtered:
            item = ListItem(Label(f"  {provider:<12} {label}"))
            item.data = (runtime, model)   # stash for retrieval
            lv.append(item)

        if self._filtered:
            lv.index = 0

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self._populate_list(event.value)
            # Show custom section only when custom row would be selected
            self._update_custom_visibility()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        runtime, model = item.data if hasattr(item, "data") else ("__custom__", "")
        self._custom_mode = (runtime == "__custom__")
        self._update_custom_visibility()
        if not self._custom_mode:
            # Pre-fill custom fields with selection for easy editing
            self.query_one("#custom-runtime", Input).value = runtime
            self.query_one("#custom-model",   Input).value = model

    def _update_custom_visibility(self) -> None:
        section = self.query_one("#custom-section")
        # Always show — fields double as a preview/override for any selection
        section.display = True

    def action_select_item(self) -> None:
        lv = self.query_one("#provider-list", ListView)
        if lv.highlighted_child:
            self.on_list_view_selected(
                ListView.Selected(lv, lv.highlighted_child)
            )

    def action_save(self) -> None:
        self._do_save()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self._do_save()
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def _do_save(self) -> None:
        # Custom fields take priority if filled in
        custom_rt    = self.query_one("#custom-runtime", Input).value.strip()
        custom_model = self.query_one("#custom-model",   Input).value.strip()

        if custom_rt and custom_model:
            runtime = custom_rt
            model   = custom_model
        else:
            # Fall back to list selection
            lv   = self.query_one("#provider-list", ListView)
            item = lv.highlighted_child
            if item and hasattr(item, "data"):
                runtime, model = item.data
            else:
                self.app.notify("Select a model or fill in custom fields.", severity="warning")
                return

        if runtime == "__custom__" or not runtime or not model:
            self.app.notify("Fill in both runtime and model fields.", severity="warning")
            return

        # Persist to config.yaml
        cfg = self._load_config()
        if "overseer" not in cfg:
            cfg["overseer"] = {}
        cfg["overseer"]["runtime"] = runtime
        cfg["overseer"]["model"]   = model
        CONFIG_PATH.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False))

        self.dismiss({"runtime": runtime, "model": model})
```

```python
# src/tui/app.py  — additions only, merge into existing file

# In SwarmApp class:

BINDINGS = [
    # ... your existing bindings ...
    Binding("m", "push_screen('model_selector')", "Model",  show=True),
]

def on_mount(self) -> None:
    # ── Autofocus overseer chat input immediately on launch ────────────────
    # Textual processes focus after compose() completes — call_after_refresh
    # ensures the widget tree is fully built before we try to focus.
    self.call_after_refresh(self._focus_chat_input)

    # ... rest of your existing on_mount logic ...

def _focus_chat_input(self) -> None:
    """Focus the overseer chat input so the user can type immediately."""
    try:
        from src.tui.panels.overseer_chat import OverseerChatPanel
        panel = self.query_one(OverseerChatPanel)
        # Try common input widget IDs — adjust to match your actual widget id
        for selector in ("#chat-input", "#overseer-input", "Input"):
            try:
                panel.query_one(selector).focus()
                return
            except Exception:
                continue
    except Exception:
        pass

def action_push_screen_model_selector(self) -> None:
    from src.tui.screens.model_selector import ModelSelectorModal

    def handle_result(result: dict | None) -> None:
        if result:
            runtime = result["runtime"]
            model   = result["model"]
            self.notify(f"Overseer: {runtime} / {model}", title="Model updated")
            # Live-reload the coordinator with new config if running
            if hasattr(self, "coordinator"):
                self.coordinator.reload_model(runtime, model)

    self.push_screen(ModelSelectorModal(), handle_result)

# Override the 'm' binding handler name to match:
def action_model(self) -> None:
    self.action_push_screen_model_selector()
```

```python
# src/tui/panels/overseer_chat.py — one addition only

class OverseerChatPanel(Widget):   # or whatever your base class is

    def on_mount(self) -> None:
        # Ensure the input inside this panel is named so app.py can find it
        # If your Input already has an id, just make sure it matches
        # the selector in SwarmApp._focus_chat_input()
        try:
            self.query_one(Input).id = "chat-input"
        except Exception:
            pass
```

```python
# Entry point addition — src/cli/main.py or wherever `swarm` console script points

import sys

def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        from src.cli.setup import run_setup
        run_setup()
        return

    # Normal TUI launch
    from src.tui.app import SwarmApp
    SwarmApp().run()
```

***

## How It All Fits Together

```
swarm setup          → terminal wizard (no TUI needed, works headless/SSH)
swarm                → launches TUI, chat input focused immediately
M key in TUI         → opens ModelSelectorModal over current screen
Escape / Cancel      → dismiss with no changes
Ctrl+S / Save        → writes runtime+model to config.yaml, notifies coordinator
```

The search filter in the modal is the key UX win — typing `openai` instantly narrows to just o3/o4-mini, typing `claude` shows only Anthropic options. Custom fields always visible at the bottom so power users can paste any `provider/model` string without needing a list entry for it.
