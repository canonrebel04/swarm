"""
Generic OpenAI-compatible provider wrapper.

Supports any API that exposes /v1/models and /v1/chat/completions:
  - OpenRouter, Groq, Together AI, DeepSeek, Fireworks
  - Local: Ollama, vLLM, LiteLLM, LocalAI, llama.cpp server
  - Custom enterprise endpoints

Configuration is stored in config.yaml under providers.openai_compat.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import aiohttp
import yaml


@dataclass
class ProviderConfig:
    """Configuration for an OpenAI-compatible provider."""
    base_url: str
    api_key: str | None = None
    model: str = "default"
    label: str = "openai-compat"

    @property
    def models_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/v1/models"

    @property
    def chat_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/v1/chat/completions"

    @property
    def headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h


def get_api_key(env_var: str) -> str | None:
    """Read API key from env or .env file."""
    val = os.environ.get(env_var)
    if val:
        return val
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line:
                key, val = line.split("=", 1)
                if key.strip() == env_var:
                    return val.strip().strip('"').strip("'")
    return None


def load_provider_config(config_path: str = "config.yaml") -> ProviderConfig | None:
    """Load OpenAI-compatible provider config from config.yaml."""
    if not Path(config_path).exists():
        return None
    cfg = yaml.safe_load(Path(config_path).read_text()) or {}
    provider = cfg.get("providers", {}).get("openai_compat")
    if not provider:
        return None

    base_url = provider.get("base_url", "")
    api_key_env = provider.get("api_key_env", "OPENAI_COMPAT_KEY")
    model = provider.get("model", "default")

    api_key = get_api_key(api_key_env)
    if api_key_env and not api_key:
        # Try direct env var lookup
        api_key = os.environ.get(api_key_env)

    return ProviderConfig(
        base_url=base_url,
        api_key=api_key,
        model=model,
        label="openai-compat",
    )


async def fetch_models(config: ProviderConfig) -> list[str]:
    """Fetch available models from an OpenAI-compatible /v1/models endpoint."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                config.models_url,
                headers=config.headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    models = [m["id"] for m in data.get("data", []) if "id" in m]
                    if models:
                        return sorted(models)
    except Exception:
        pass
    return [config.model] if config.model != "default" else ["default"]


async def chat_completion(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> dict | None:
    """Send a chat completion request to the provider.

    Returns the full response dict, or None on failure.
    """
    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                config.chat_url,
                headers=config.headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception:
        pass
    return None


async def check_health(config: ProviderConfig) -> bool:
    """Check if the provider is reachable and responding."""
    try:
        models = await fetch_models(config)
        return len(models) > 0
    except Exception:
        return False
