"""Gemini LLM provider using google-genai SDK."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from google import genai
from google.genai import types

from kresearch.config import KResearchConfig
from kresearch.providers.base import ChatSession, ProviderInterface
from kresearch.providers.gemini.chat import GeminiChatSession
from kresearch.providers.types import (
    FunctionCall, GenerateResponse, Message, ModelInfo, TokenUsageInfo, ToolDeclaration,
)

DEFAULT_MODEL = "gemini-3-flash-preview"
FAST_MODEL = "gemini-3.1-flash-lite-preview"


class GeminiProvider(ProviderInterface):
    """Provider backed by Google's Gemini API."""

    def __init__(self, config: KResearchConfig) -> None:
        proxy = config.get_proxy("gemini")
        http_opts = {"proxy": proxy} if proxy else None
        self._client = genai.Client(api_key=config.gemini_api_key, http_options=http_opts)
        self._model = config.model

    def _convert_tools(self, tools: list[ToolDeclaration] | None) -> list | None:
        if not tools:
            return None
        return [types.FunctionDeclaration(
            name=t.name, description=t.description, parameters=t.parameters or None,
        ) for t in tools]

    def _to_response(self, raw: Any) -> GenerateResponse:
        if not raw.candidates:
            return GenerateResponse()
        text, thinking = "", ""
        func_calls: list[FunctionCall] = []
        parts = raw.candidates[0].content.parts if raw.candidates[0].content else []
        for part in parts:
            if hasattr(part, "thought") and part.thought:
                thinking += part.text or ""
            elif part.function_call:
                fc = part.function_call
                func_calls.append(FunctionCall(name=fc.name, args=dict(fc.args or {})))
            elif part.text:
                text += part.text
        usage = TokenUsageInfo()
        if raw.usage_metadata:
            usage.input_tokens = raw.usage_metadata.prompt_token_count or 0
            usage.output_tokens = raw.usage_metadata.candidates_token_count or 0
        return GenerateResponse(text=text, function_calls=func_calls,
                                thinking=thinking, usage=usage, raw={})

    def _make_config(self, system_instruction=None, tool_decls=None):
        return types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[types.Tool(function_declarations=tool_decls)] if tool_decls else None,
            thinking_config=types.ThinkingConfig(thinking_budget=-1),
        )

    async def generate(self, messages: list[Message], *, system_instruction=None,
                       tools=None, thinking_level=None) -> GenerateResponse:
        cfg = self._make_config(system_instruction, self._convert_tools(tools))
        contents = [{"role": m.role, "parts": [{"text": m.content}]} for m in messages]
        raw = await self._client.aio.models.generate_content(
            model=self._model, contents=contents, config=cfg)
        return self._to_response(raw)

    async def generate_stream(self, messages: list[Message], *, system_instruction=None,
                              tools=None, thinking_level=None) -> AsyncIterator[str]:
        cfg = self._make_config(system_instruction)
        contents = [{"role": m.role, "parts": [{"text": m.content}]} for m in messages]
        async for chunk in self._client.aio.models.generate_content_stream(
            model=self._model, contents=contents, config=cfg,
        ):
            if chunk.text:
                yield chunk.text

    async def create_chat(self, *, system_instruction=None, tools=None,
                          thinking_level=None) -> ChatSession:
        cfg = self._make_config(system_instruction, self._convert_tools(tools))
        raw_chat = self._client.aio.chats.create(model=self._model, config=cfg)
        return GeminiChatSession(raw_chat)

    def list_models(self) -> list[ModelInfo]:
        models: list[ModelInfo] = []
        for m in self._client.models.list():
            if "generateContent" in (m.supported_generation_methods or []):
                models.append(ModelInfo(
                    id=(m.name or "").replace("models/", ""),
                    name=m.display_name or m.name or "",
                    context_window=m.input_token_limit or 0,
                ))
        return models
