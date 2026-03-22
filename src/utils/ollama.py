from .openai_compat import fetch_openai_compatible_models

# Hardcoded fallback list for Ollama/Hermes
FALLBACK_MODELS = [
    "hermes",
    "llama3",
    "mistral",
    "phi3",
]

async def fetch_ollama_models() -> list[str]:
    """
    Fetch available models from local Ollama /v1/models endpoint.
    Returns FALLBACK_MODELS if request fails.
    """
    # Ollama by default provides OpenAI compatible endpoint at /v1
    # No API key needed for local Ollama usually
    return await fetch_openai_compatible_models(
        base_url="http://localhost:11434/v1",
        api_key="ollama", # placeholder
        fallback_models=FALLBACK_MODELS
    )
