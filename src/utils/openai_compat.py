import os
import asyncio
from pathlib import Path
import aiohttp

async def fetch_openai_compatible_models(
    base_url: str, 
    api_key: str | None, 
    fallback_models: list[str]
) -> list[str]:
    """
    Fetch available models from an OpenAI-compatible /v1/models endpoint.
    Returns fallback_models if key is missing or request fails.
    """
    if not api_key:
        return fallback_models

    # Ensure base_url doesn't end with a slash for consistent joining
    base_url = base_url.rstrip("/")
    url = f"{base_url}/v1/models"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Standard OpenAI response format: {"object": "list", "data": [{"id": "...", ...}, ...]}
                    models = [m["id"] for m in data.get("data", []) if "id" in m]
                    if models:
                        return sorted(models)
    except Exception:
        pass

    return fallback_models

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
