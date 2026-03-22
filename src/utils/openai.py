from .openai_compat import fetch_openai_compatible_models, get_api_key

# Hardcoded fallback list for OpenAI
FALLBACK_MODELS = [
    "o3-mini",
    "o1-preview",
    "o1-mini",
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
]

async def fetch_openai_models() -> list[str]:
    """
    Fetch available models from OpenAI /v1/models endpoint.
    Returns FALLBACK_MODELS if key is missing or request fails.
    """
    api_key = get_api_key("OPENAI_API_KEY")
    return await fetch_openai_compatible_models(
        base_url="https://api.openai.com",
        api_key=api_key,
        fallback_models=FALLBACK_MODELS
    )
