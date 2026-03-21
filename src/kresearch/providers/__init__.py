"""Provider factory — maps provider names to implementations."""

from __future__ import annotations

from kresearch.config import KResearchConfig
from kresearch.providers.base import ProviderInterface

PROVIDER_REGISTRY: dict[str, str] = {
    "gemini": "kresearch.providers.gemini.provider.GeminiProvider",
    "openai": "kresearch.providers.openai.provider.OpenaiProvider",
    "custom": "kresearch.providers.custom.provider.CustomProvider",
    "anthropic": "kresearch.providers.anthropic",
    "xai": "kresearch.providers.xai",
    "perplexity": "kresearch.providers.perplexity",
}


def get_provider(config: KResearchConfig) -> ProviderInterface:
    """Instantiate the configured provider."""
    name = config.provider.lower()
    if name not in PROVIDER_REGISTRY:
        raise ValueError(
            f"Unknown provider '{name}'. "
            f"Available: {', '.join(PROVIDER_REGISTRY)}"
        )
    import importlib

    module_path = PROVIDER_REGISTRY[name]
    if "." in module_path and module_path.rsplit(".", 1)[-1][0].isupper():
        mod_path, cls_name = module_path.rsplit(".", 1)
        mod = importlib.import_module(mod_path)
        cls = getattr(mod, cls_name)
    else:
        mod = importlib.import_module(module_path)
        cls = getattr(mod, f"{name.capitalize()}Provider")
    return cls(config)
