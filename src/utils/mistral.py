from .openai_compat import fetch_openai_compatible_models, get_api_key

# Hardcoded fallback list in case API fails or key is missing
FALLBACK_MODELS = [
    "mistral-large-latest",
    "mistral-large-2407",
    "mistral-large-2402",
    "mistral-medium-latest",
    "mistral-medium-2312",
    "mistral-small-latest",
    "mistral-small-2402",
    "codestral-latest",
    "codestral-2405",
    "codestral-mamba-latest",
    "open-codestral-mamba",
    "open-mistral-nemo",
    "mistral-small-3.1",
    "mistral-medium-3",
    "magistral-medium-latest",
    "magistral-small-latest",
    "mistralai/Mistral-7B-Instruct-v0.3",
    "mistralai/Mixtral-8x7B-Instruct-v0.1",
]

async def fetch_mistral_models() -> list[str]:
    """
    Fetch available models from Mistral /v1/models endpoint.
    Returns FALLBACK_MODELS if key is missing or request fails.
    """
    api_key = get_api_key("MISTRAL_API_KEY")
    return await fetch_openai_compatible_models(
        base_url="https://api.mistral.ai",
        api_key=api_key,
        fallback_models=FALLBACK_MODELS
    )
