"""OpenAI provider — not yet implemented."""

DEFAULT_MODEL = "gpt-4o"
FAST_MODEL = "gpt-4o-mini"


class OpenaiProvider:
    def __init__(self, config):
        raise NotImplementedError(
            "OpenAI provider is not yet implemented. "
            "Install: pip install kresearch[openai]"
        )
