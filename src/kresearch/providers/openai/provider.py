"""OpenAI LLM provider using the openai SDK."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from openai import AsyncOpenAI, DefaultAsyncHttpxClient

from kresearch.config import KResearchConfig
from kresearch.providers.base import ChatSession, ProviderInterface
from kresearch.providers.openai.chat import OpenaiChatSession
from kresearch.providers.types import (
    FunctionCall, GenerateResponse, Message, ModelInfo, TokenUsageInfo, ToolDeclaration,
)

DEFAULT_MODEL = "gpt-4o"
FAST_MODEL = "gpt-4o-mini"


class OpenaiProvider(ProviderInterface):
    """Provider backed by the OpenAI API."""

    def __init__(self, config: KResearchConfig) -> None:
        api_key = config.openai_api_key
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI provider.")
        proxy = config.get_proxy("openai")
        http_client = DefaultAsyncHttpxClient(proxy=proxy) if proxy else None
        self._client = AsyncOpenAI(api_key=api_key, http_client=http_client)
        self._model = config.model if config.model != "gemini-3-flash-preview" else DEFAULT_MODEL

    @staticmethod
    def _convert_tools(tools: list[ToolDeclaration] | None) -> list[dict] | None:
        if not tools:
            return None
        return [{"type": "function", "function": {
            "name": t.name, "description": t.description,
            "parameters": t.parameters or {"type": "object", "properties": {}},
        }} for t in tools]

    @staticmethod
    def _to_response(raw: Any) -> GenerateResponse:
        choice = raw.choices[0] if raw.choices else None
        if not choice:
            return GenerateResponse()
        msg = choice.message
        text = msg.content or ""
        func_calls: list[FunctionCall] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                func_calls.append(FunctionCall(name=tc.function.name, args=args))
        usage = TokenUsageInfo()
        if raw.usage:
            usage.input_tokens = raw.usage.prompt_tokens or 0
            usage.output_tokens = raw.usage.completion_tokens or 0
        return GenerateResponse(text=text, function_calls=func_calls, usage=usage, raw={})

    async def generate(self, messages: list[Message], *, system_instruction: str | None = None,
                       tools: list[ToolDeclaration] | None = None,
                       thinking_level: str | None = None) -> GenerateResponse:
        msgs: list[dict[str, str]] = []
        if system_instruction:
            msgs.append({"role": "system", "content": system_instruction})
        for m in messages:
            msgs.append({"role": m.role, "content": m.content})
        kwargs: dict[str, Any] = {"model": self._model, "messages": msgs}
        converted = self._convert_tools(tools)
        if converted:
            kwargs["tools"] = converted
        raw = await self._client.chat.completions.create(**kwargs)
        return self._to_response(raw)

    async def generate_stream(self, messages: list[Message], *,
                              system_instruction: str | None = None,
                              tools: list[ToolDeclaration] | None = None,
                              thinking_level: str | None = None) -> AsyncIterator[str]:
        msgs: list[dict[str, str]] = []
        if system_instruction:
            msgs.append({"role": "system", "content": system_instruction})
        for m in messages:
            msgs.append({"role": m.role, "content": m.content})
        stream = await self._client.chat.completions.create(
            model=self._model, messages=msgs, stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def create_chat(self, *, system_instruction: str | None = None,
                          tools: list[ToolDeclaration] | None = None,
                          thinking_level: str | None = None) -> ChatSession:
        return OpenaiChatSession(
            client=self._client, model=self._model,
            system_instruction=system_instruction,
            tools=self._convert_tools(tools),
        )

    def list_models(self) -> list[ModelInfo]:
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self._list_models_async())

    async def _list_models_async(self) -> list[ModelInfo]:
        models: list[ModelInfo] = []
        async for m in self._client.models.list():
            models.append(ModelInfo(id=m.id, name=m.id))
        return models
