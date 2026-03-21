"""Custom OpenAI-compatible provider — any endpoint with an API key and base URL."""

from __future__ import annotations

from openai import AsyncOpenAI, DefaultAsyncHttpxClient

from kresearch.config import KResearchConfig
from kresearch.providers.openai.provider import OpenaiProvider

DEFAULT_MODEL = "gpt-4o"
FAST_MODEL = "gpt-4o-mini"


class CustomProvider(OpenaiProvider):
    """Thin wrapper over OpenaiProvider that uses a custom base_url and api_key."""

    def __init__(self, config: KResearchConfig) -> None:
        if not config.custom_api_key:
            raise ValueError(
                "KRESEARCH_CUSTOM_API_KEY is required for the custom provider."
            )
        if not config.custom_api_base:
            raise ValueError(
                "KRESEARCH_CUSTOM_API_BASE is required for the custom provider. "
                "Example: https://api.deepseek.com/v1"
            )
        proxy = config.get_proxy("custom")
        http_client = DefaultAsyncHttpxClient(proxy=proxy) if proxy else None
        self._client = AsyncOpenAI(
            api_key=config.custom_api_key,
            base_url=config.custom_api_base,
            http_client=http_client,
        )
        self._model = config.model if config.model != "gemini-3-flash-preview" else DEFAULT_MODEL
