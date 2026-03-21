"""Application configuration via environment variables and CLI."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings


class KResearchConfig(BaseSettings):
    """Configuration loaded from env vars, .env file, and CLI overrides."""

    model_config = {
        "env_prefix": "KRESEARCH_", "env_file": ".env",
        "extra": "ignore", "populate_by_name": True,
    }

    # Provider selection
    provider: str = "gemini"

    # Model defaults (validated against API at runtime)
    model: str = "gemini-3-flash-preview"
    fast_model: str = "gemini-3.1-flash-lite-preview"

    # API keys (loaded from env)
    gemini_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    custom_api_key: str = ""
    custom_api_base: str = ""  # e.g. "https://api.deepseek.com/v1"

    # Proxy settings
    proxy: str | None = None
    gemini_proxy: str | None = None
    openai_proxy: str | None = None
    custom_proxy: str | None = None

    # Agent behaviour
    max_iterations: int = 20  # 0 = unlimited
    max_concurrent_subagents: int = 3
    thinking_level: str = "high"

    # Output
    verbose: bool = False
    output_dir: str = "."

    # Web UI
    web_host: str = "127.0.0.1"
    web_port: int = 8000
    web_db_path: str = ""

    def get_proxy(self, provider: str | None = None) -> str | None:
        """Return the most specific proxy for the given provider."""
        provider_proxy = getattr(self, f"{provider}_proxy", None) if provider else None
        return provider_proxy or self.proxy
