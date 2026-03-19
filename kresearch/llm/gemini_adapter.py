"""Google Gemini SDK adapter using the modern google-genai package."""

from __future__ import annotations

from typing import AsyncIterator


class GeminiAdapter:
    """Wraps the google-genai SDK."""

    def __init__(self, api_key: str):
        from google import genai
        self._client = genai.Client(api_key=api_key)

    async def complete(self, contents, model, temperature,
                       max_tokens, json_mode, system_instruction):
        from google.genai import types

        cfg = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        if system_instruction:
            cfg.system_instruction = system_instruction
        if json_mode:
            cfg.response_mime_type = "application/json"

        resp = await self._client.aio.models.generate_content(
            model=model, contents=contents, config=cfg,
        )
        usage = getattr(resp, "usage_metadata", None)
        return {
            "content": resp.text or "",
            "model": model,
            "usage": {
                "input_tokens": getattr(usage, "prompt_token_count", 0),
                "output_tokens": getattr(usage, "candidates_token_count", 0),
            },
        }

    async def stream(self, contents, model, temperature,
                     max_tokens, system_instruction) -> AsyncIterator[str]:
        from google.genai import types

        cfg = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        if system_instruction:
            cfg.system_instruction = system_instruction

        async for chunk in self._client.aio.models.generate_content_stream(
            model=model, contents=contents, config=cfg,
        ):
            if chunk.text:
                yield chunk.text


def create_adapter(api_key: str):
    """Create a Gemini SDK adapter."""
    return GeminiAdapter(api_key)
