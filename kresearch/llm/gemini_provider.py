"""Google Gemini LLM provider using the google-genai SDK."""

from __future__ import annotations

import os
from typing import AsyncIterator

from .base import LLMProvider
from .models import GEMINI_MODELS
from .registry import register


def _sdk_available() -> bool:
    """Check if the google-genai SDK is installed."""
    try:
        from google import genai  # noqa: F401
        return True
    except ImportError:
        return False


def _resolve_api_key(api_key: str | None) -> str | None:
    """Return a non-empty API key or None."""
    if api_key:
        return api_key
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        val = os.environ.get(var, "").strip()
        if val:
            return val
    return None


class GeminiProvider(LLMProvider):
    """Provider backed by the google-genai SDK."""

    def __init__(self, api_key: str | None = None, **kwargs):
        super().__init__(api_key=_resolve_api_key(api_key), **kwargs)
        self._adapter = None

    def _ensure_adapter(self):
        if self._adapter is None:
            if not self._api_key:
                raise RuntimeError(
                    "Gemini API key not set. Set GEMINI_API_KEY or "
                    "GOOGLE_API_KEY in your .env file."
                )
            from .gemini_adapter import create_adapter
            self._adapter = create_adapter(self._api_key)

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def available_models(self) -> list[str]:
        return list(GEMINI_MODELS)

    def is_available(self) -> bool:
        return _sdk_available() and bool(self._api_key)

    def supports_json_mode(self) -> bool:
        return True

    def supports_grounding(self) -> bool:
        return True

    def _extract_system(self, messages: list[dict], system_prompt: str | None):
        parts: list[str] = []
        if system_prompt:
            parts.append(system_prompt)
        for m in messages:
            if m.get("role") == "system":
                parts.append(m["content"])
        return "\n\n".join(parts) if parts else None

    def _build_contents(self, messages: list[dict]):
        out = []
        for msg in messages:
            role = msg.get("role", "user")
            if role == "system":
                continue
            gr = "model" if role == "assistant" else "user"
            out.append({"role": gr, "parts": [msg["content"]]})
        return out

    async def complete(self, messages, model, temperature=0.7,
                       max_tokens=4096, json_mode=False,
                       system_prompt=None) -> dict:
        self._ensure_adapter()
        sys_inst = self._extract_system(messages, system_prompt)
        contents = self._build_contents(messages)
        return await self._adapter.complete(
            contents, model, temperature, max_tokens, json_mode, sys_inst,
        )

    async def stream(self, messages, model, temperature=0.7,
                     max_tokens=4096, system_prompt=None) -> AsyncIterator[str]:
        self._ensure_adapter()
        sys_inst = self._extract_system(messages, system_prompt)
        contents = self._build_contents(messages)
        async for chunk in self._adapter.stream(
            contents, model, temperature, max_tokens, sys_inst,
        ):
            yield chunk


register("gemini", GeminiProvider)
