"""Model constants and dynamic model fetching for LLM providers."""

from __future__ import annotations

# Suggested models per provider (not exhaustive -- providers accept any valid model ID).
OPENAI_MODELS: list[str] = ["gpt-4o", "gpt-4o-mini", "o3-mini"]
ANTHROPIC_MODELS: list[str] = ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"]
GEMINI_MODELS: list[str] = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"]
GROK_MODELS: list[str] = ["grok-3", "grok-3-mini"]
PERPLEXITY_MODELS: list[str] = ["sonar", "sonar-pro"]
DEEPSEEK_MODELS: list[str] = ["deepseek-chat", "deepseek-reasoner"]
OLLAMA_MODELS: list[str] = ["llama3", "mistral", "phi3", "gemma"]

ALL_MODELS: dict[str, list[str]] = {
    "openai": OPENAI_MODELS,
    "anthropic": ANTHROPIC_MODELS,
    "gemini": GEMINI_MODELS,
    "grok": GROK_MODELS,
    "perplexity": PERPLEXITY_MODELS,
    "deepseek": DEEPSEEK_MODELS,
    "ollama": OLLAMA_MODELS,
}

DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-20250514",
    "gemini": "gemini-2.5-flash",
    "grok": "grok-3",
    "perplexity": "sonar-pro",
    "deepseek": "deepseek-chat",
    "ollama": "llama3",
}

# API endpoints for listing models dynamically.
_LIST_ENDPOINTS: dict[str, str] = {
    "openai": "https://api.openai.com/v1/models",
    "deepseek": "https://api.deepseek.com/v1/models",
    "grok": "https://api.x.ai/v1/models",
    "ollama": "http://localhost:11434/api/tags",
}


async def fetch_available_models(
    provider: str,
    api_key: str | None = None,
) -> list[str] | None:
    """Fetch live model list from a provider's API.

    Returns a sorted list of model IDs, or ``None`` if the provider
    does not support listing or the request fails.
    """
    provider = provider.lower()
    try:
        if provider == "gemini":
            return await _fetch_gemini_models(api_key)
        if provider == "ollama":
            return await _fetch_ollama_models()
        if provider == "anthropic":
            return await _fetch_anthropic_models(api_key)
        endpoint = _LIST_ENDPOINTS.get(provider)
        if endpoint and api_key:
            return await _fetch_openai_compat(endpoint, api_key)
    except Exception:
        pass
    return None


async def _fetch_openai_compat(endpoint: str, api_key: str) -> list[str]:
    import httpx
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            endpoint, headers={"Authorization": f"Bearer {api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()
    return sorted(m["id"] for m in data.get("data", []))


async def _fetch_gemini_models(api_key: str | None) -> list[str]:
    import asyncio
    if not api_key:
        return None  # type: ignore[return-value]
    from google import genai
    client = genai.Client(api_key=api_key)
    models = await asyncio.to_thread(
        lambda: [m.name for m in client.models.list()]
    )
    return sorted(models)


async def _fetch_ollama_models() -> list[str]:
    import httpx
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get("http://localhost:11434/api/tags")
        resp.raise_for_status()
        data = resp.json()
    return sorted(m["name"] for m in data.get("models", []))


async def _fetch_anthropic_models(api_key: str | None) -> list[str]:
    import httpx
    if not api_key:
        return None  # type: ignore[return-value]
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return sorted(m["id"] for m in data.get("data", []))
