"""Gemini chat session wrapper with proper batch function-response support."""

from __future__ import annotations

from typing import Any

from google.genai import types

from kresearch.providers.base import ChatSession
from kresearch.providers.types import (
    FunctionCall,
    GenerateResponse,
    Message,
    TokenUsageInfo,
)


class GeminiChatSession(ChatSession):
    """Wraps google-genai's async chat into our ChatSession interface."""

    def __init__(self, raw_chat: Any) -> None:
        self._chat = raw_chat
        self._history: list[Message] = []

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
                func_calls.append(
                    FunctionCall(name=fc.name, args=dict(fc.args or {}))
                )
            elif part.text:
                text += part.text
        usage = TokenUsageInfo()
        if raw.usage_metadata:
            usage.input_tokens = raw.usage_metadata.prompt_token_count or 0
            usage.output_tokens = raw.usage_metadata.candidates_token_count or 0
        return GenerateResponse(
            text=text, function_calls=func_calls,
            thinking=thinking, usage=usage, raw={},
        )

    async def send(self, message: str) -> GenerateResponse:
        self._history.append(Message(role="user", content=message))
        raw = await self._chat.send_message(message)
        resp = self._to_response(raw)
        self._history.append(Message(role="assistant", content=resp.text))
        return resp

    async def send_function_response(
        self, name: str, response: dict
    ) -> GenerateResponse:
        part = types.Part(
            function_response=types.FunctionResponse(name=name, response=response)
        )
        raw = await self._chat.send_message(part)
        resp = self._to_response(raw)
        self._history.append(Message(role="assistant", content=resp.text))
        return resp

    async def send_function_responses(
        self, responses: list[tuple[str, dict]]
    ) -> GenerateResponse:
        """Send ALL function results in a single message (correct Gemini behavior)."""
        parts = [
            types.Part(
                function_response=types.FunctionResponse(name=name, response=resp)
            )
            for name, resp in responses
        ]
        raw = await self._chat.send_message(parts)
        resp = self._to_response(raw)
        self._history.append(Message(role="assistant", content=resp.text))
        return resp

    def get_history(self) -> list[Message]:
        return list(self._history)
