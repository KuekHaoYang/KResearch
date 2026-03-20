"""Anthropic provider — not yet implemented."""

DEFAULT_MODEL = "claude-sonnet-4-6"
FAST_MODEL = "claude-haiku-4-5"


class AnthropicProvider:
    def __init__(self, config):
        raise NotImplementedError(
            "Anthropic provider is not yet implemented. "
            "Install: pip install kresearch[anthropic]"
        )
