# OpenAI-Compatible Provider Support — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Swarm setup wizard and config system supports arbitrary OpenAI-compatible APIs (OpenRouter, Together, Groq, vLLM, local endpoints, etc.) — not just hardcoded providers.

**Architecture:** Extend the `swarm setup` wizard with an "OpenAI-compatible" provider type that collects base_url + api_key, fetches models via `/v1/models`, and stores config. Add a generic `openai_compat` utility wrapper that all runtimes can use with custom endpoints.

**Tech Stack:** Python 3.12+, aiohttp, yaml, existing openai_compat.py utilities

---

## Current State

| Provider | Hardcoded? | base_url | api_key |
|----------|-----------|----------|---------|
| Anthropic | Yes | N/A | ANTHROPIC_API_KEY |
| OpenAI | Yes | api.openai.com | OPENAI_API_KEY |
| Mistral | Yes | api.mistral.ai | MISTRAL_API_KEY |
| Google | Yes | N/A | GOOGLE_API_KEY |
| Ollama | Yes | localhost:11434 | None |
| Custom | Stub | - | - |

## Target State

| Provider | base_url | api_key | How |
|----------|----------|---------|-----|
| Anthropic | - | env var | existing |
| OpenAI | - | env var | existing |
| Mistral | - | env var | existing |
| Google | - | env var | existing |
| Ollama | - | none | existing |
| **OpenAI-compat** | **user-entered** | **user-entered** | **NEW** |

---

### Task 1: Add OpenAI-compatible provider entry to setup wizard

**Objective:** User can select "OpenAI-compatible" in setup, enter base URL + API key, see models, pick one.

**Files:**
- Modify: `src/cli/setup.py`

**Step 1: Add PROVIDER_CATALOG entry**

Replace the stub "Custom" entry with:
```python
("OpenAI-compatible · any v1 API endpoint", "__openai_compat__", "__dynamic__", None),
```

**Step 2: Add base_url + api_key collection for __openai_compat__**

After the dynamic model selection block (line 127-163), add a branch for `__openai_compat__`:
```python
if runtime_key == "__openai_compat__":
    # Ask for base URL
    print(_bold("  Configure OpenAI-compatible endpoint"))
    base_url = input("  Base URL (e.g. https://api.openrouter.ai): ").strip()
    # Ask for API key
    api_key = _secure_input("  API Key: ")
    env_var_name = input("  Env var name [OPENAI_COMPAT_KEY]: ").strip() or "OPENAI_COMPAT_KEY"
    if api_key:
        _write_env_file(env_var_name, api_key)
    # Fetch models
    models = await _fetch_models_via_api(base_url, api_key, ["default"])
    # ... model selection ...
    # Save to config
    cfg["providers"] = cfg.get("providers", {})
    cfg["providers"]["openai_compat"] = {
        "base_url": base_url,
        "api_key_env": env_var_name,
        "model": model_str,
        "label": "OpenAI-compatible",
    }
```

**Step 3: Update _default_runtime_block**

Add `__openai_compat__` entry pointing to vibe or codex as the executor.

**Step 4: Verify**

Run `swarm setup`, select OpenAI-compatible, enter an OpenRouter URL + key.

---

### Task 2: Add openai_compat provider utility

**Objective:** A reusable module that wraps any OpenAI-compatible endpoint for model listing and chat.

**Files:**
- Create: `src/utils/provider.py`

**Step 1: Write ProviderConfig dataclass**

```python
@dataclass
class ProviderConfig:
    base_url: str
    api_key: str | None
    model: str
    label: str = "openai-compat"
```

**Step 2: Write fetch_models and chat_completion functions**

Reuse existing `fetch_openai_compatible_models` for model listing.
Add a `chat_completion` function for sending prompts.

**Step 3: Test with a real endpoint**

Test against OpenRouter or a local Ollama instance.

---

### Task 3: Update runtime_config.py to support custom providers

**Objective:** The RuntimeConfig class can load and use custom OpenAI-compatible providers from config.yaml.

**Files:**
- Modify: `src/cli/runtime_config.py`

**Step 1: Add provider loading to _load_config**

Read `providers` section from config.yaml, populate model_providers dynamically.

**Step 2: Update scan_provider_models to use auth headers**

Currently sends no auth — OpenAI-compatible endpoints need `Authorization: Bearer`.

**Step 3: Verify**

---

### Task 4: End-to-end test

**Objective:** Full flow works: setup → config → model fetch → saved config.

**Step 1:** Run `swarm setup`, select OpenAI-compatible
**Step 2:** Enter an endpoint + key
**Step 3:** Verify models appear in selection
**Step 4:** Verify config.yaml has provider entry
**Step 5:** Verify `swarm doctor` sees the provider
