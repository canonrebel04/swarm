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
from textual.containers import Vertical, Horizontal
from textual.binding import Binding
import yaml
import shutil
import os

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

# Runtime registry for auto-detection
RUNTIME_REGISTRY = [
    ("claude-code", "claude", "Claude Code", "ANTHROPIC_API_KEY"),
    ("vibe", "vibe", "Vibe (Mistral)", "MISTRAL_API_KEY"),
    ("codex", "codex", "OpenAI Codex", "OPENAI_API_KEY"),
    ("gemini", "gemini", "Gemini CLI", "GOOGLE_API_KEY"),
    ("hermes", "hermes", "Hermes Agent", None),
]


def _read_env(key: str) -> str | None:
    """Check os.environ then .env file."""
    val = os.environ.get(key)
    if val:
        return val
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _runtime_status(runtime_key: str, binary: str, env_var: str | None) -> str:
    """Return a status badge string for a runtime."""
    has_binary = shutil.which(binary) is not None
    has_key    = (env_var is None) or bool(_read_env(env_var))

    if has_binary and has_key:
        return "ready"
    elif has_binary and not has_key:
        return "no-key"
    else:
        return "missing"


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        return yaml.safe_load(CONFIG_PATH.read_text()) or {}
    return {}


def _save_config(runtime: str, model: str) -> None:
    cfg = _load_config()
    if "overseer" not in cfg:
        cfg["overseer"] = {}
    cfg["overseer"]["runtime"] = runtime
    cfg["overseer"]["model"]   = model
    CONFIG_PATH.write_text(yaml.dump(cfg, default_flow_style=False, sort_keys=False))


class ModelSelectorModal(ModalScreen):
    """Full-screen modal for selecting overseer model and provider."""

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Cancel", show=True),
        Binding("ctrl+s", "save",          "Save",   show=True),
        Binding("enter", "select_item",   "Select", show=False),
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

    #current-label {
        text-align: center;
        color: $text-muted;
        padding: 1 0 0 0;
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

    .badge-ready   { color: #00ff88; }
    .badge-no-key  { color: #ffaa00; }
    .badge-missing { color: #ff4466; }
    """

    def __init__(self) -> None:
        super().__init__()
        self._cfg = _load_config()
        self._filtered = list(PROVIDER_OPTIONS)
        self._custom_mode = False
        self._selected_rt = self._cfg.get("overseer", {}).get("runtime", "vibe")
        self._selected_model = self._cfg.get("overseer", {}).get("model", "mistral-large-latest")
        # Pre-compute statuses
        self._statuses = {
            rt: _runtime_status(rt, binary, env_var)
            for rt, binary, _, env_var in RUNTIME_REGISTRY
        }

    def compose(self) -> ComposeResult:
        cur_rt    = self._selected_rt
        cur_model = self._selected_model

        with Vertical(id="modal-container"):
            yield Static("⚙  Overseer Model Selector", id="modal-title")
            yield Static(
                f"Current: [{cur_rt}] {cur_model}",
                id="current-label"
            )
            yield Rule(id="divider")

            # Program selector with auto-detection
            yield Static("① Select Program", classes="section-label")
            yield ListView(*self._make_program_items(), id="program-list")

            yield Rule()

            # Model selector
            yield Static("② Select Model", classes="section-label")
            yield ListView(id="model-list")

            yield Rule()

            # Custom override
            yield Static("③ Custom Override (optional)", classes="section-label")
            with Horizontal(id="custom-row"):
                yield Label("Runtime key:")
                yield Input(placeholder="e.g. vibe", id="custom-runtime")
                yield Label("Model:")
                yield Input(placeholder="e.g. mistral-large-latest", id="custom-model")

            with Horizontal(id="button-row"):
                yield Button("Cancel",    id="btn-cancel",  variant="default")
                yield Button("Save  ⌃S",  id="btn-save",    variant="primary")

    def _make_program_items(self) -> list[ListItem]:
        items = []
        for rt, binary, display, env_var in RUNTIME_REGISTRY:
            status = self._statuses[rt]
            if status == "ready":
                badge   = "✓"
                cls     = "badge-ready"
                note    = "ready"
            elif status == "no-key":
                badge   = "⚠"
                cls     = "badge-no-key"
                key_name = env_var or ""
                note    = f"missing {key_name}"
            else:
                badge   = "✗"
                cls     = "badge-missing"
                note    = "not installed"

            label_text = f"  {badge}  {display:<20}  {note}"
            item = ListItem(Static(label_text, classes=cls))
            item.data = rt
            items.append(item)
        return items

    def _make_model_items(self, runtime_key: str) -> list[ListItem]:
        items = []
        for runtime, model, provider, label in PROVIDER_OPTIONS:
            if runtime == runtime_key:
                item = ListItem(Static(f"  {label}"))
                item.data = model
                items.append(item)
        return items

    def on_mount(self) -> None:
        self._refresh_model_list(self._selected_rt)
        # Highlight the currently configured program
        pl = self.query_one("#program-list", ListView)
        for i, (rt, *_) in enumerate(RUNTIME_REGISTRY):
            if rt == self._selected_rt:
                pl.index = i
                break
        pl.focus()

    def _refresh_model_list(self, runtime_key: str) -> None:
        ml = self.query_one("#model-list", ListView)
        ml.clear()
        for item in self._make_model_items(runtime_key):
            ml.append(item)
        # Pre-highlight current model if it matches
        for i, (runtime, model, _, _) in enumerate(PROVIDER_OPTIONS):
            if runtime == runtime_key and model == self._selected_model:
                ml.index = i
                return
        if ml._nodes:
            ml.index = 0

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id == "program-list":
            item = event.item
            if item and hasattr(item, "data"):
                rt = item.data
                self._selected_rt = rt
                self._refresh_model_list(rt)
                # Auto-select first model
                ml = self.query_one("#model-list", ListView)
                if ml._nodes:
                    ml.index = 0
                    first = ml._nodes[0]
                    if hasattr(first, "data"):
                        self._selected_model = first.data

        elif event.list_view.id == "model-list":
            item = event.item
            if item and hasattr(item, "data"):
                self._selected_model = item.data

    def action_select_item(self) -> None:
        lv = self.query_one("#program-list", ListView)
        if lv.highlighted_child:
            item = lv.highlighted_child
            if hasattr(item, "data"):
                rt = item.data
                self._selected_rt = rt
                self._refresh_model_list(rt)
                ml = self.query_one("#model-list", ListView)
                if ml._nodes:
                    ml.index = 0
                    first = ml._nodes[0]
                    if hasattr(first, "data"):
                        self._selected_model = first.data

    def action_save(self) -> None:
        self._do_save()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self._do_save()
        elif event.button.id == "btn-cancel":
            self.dismiss(None)

    def _do_save(self) -> None:
        # Custom fields take priority if filled in
        c_rt    = self.query_one("#custom-runtime", Input).value.strip()
        c_model = self.query_one("#custom-model",   Input).value.strip()

        runtime = c_rt    if c_rt    else self._selected_rt
        model   = c_model if c_model else self._selected_model

        if not runtime or not model:
            self.app.notify("Select a program and model.", severity="warning")
            return

        _save_config(runtime, model)
        self.dismiss({"runtime": runtime, "model": model})
