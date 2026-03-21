"""Gemini chat session with retry logic for rate limits."""
from __future__ import annotations
import asyncio, logging
from typing import Any
from google.genai import types
from kresearch.providers.base import ChatSession
from kresearch.providers.types import (
    FunctionCall, GenerateResponse, Message, TokenUsageInfo,
)

log = logging.getLogger(__name__)
MAX_RETRIES = 5


class GeminiChatSession(ChatSession):
    """Wraps google-genai async chat with automatic retry on rate limits."""

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
                func_calls.append(FunctionCall(name=fc.name, args=dict(fc.args or {})))
            elif part.text:
                text += part.text
        usage = TokenUsageInfo()
        if raw.usage_metadata:
            usage.input_tokens = raw.usage_metadata.prompt_token_count or 0
            usage.output_tokens = raw.usage_metadata.candidates_token_count or 0
        return GenerateResponse(
            text=text, function_calls=func_calls, thinking=thinking, usage=usage, raw={},
        )

    async def _send_with_retry(self, message: Any) -> Any:
        """Send a message with exponential backoff on rate limit errors."""
        for attempt in range(MAX_RETRIES):
            try:
                return await self._chat.send_message(message)
            except Exception as e:
                err_str = str(e).lower()
                is_rate_limit = "429" in err_str or "resource_exhausted" in err_str
                is_server_err = "500" in err_str or "503" in err_str
                if (is_rate_limit or is_server_err) and attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt + 1
                    log.warning("API error (attempt %d/%d), retrying in %ds: %s",
                                attempt + 1, MAX_RETRIES, wait, str(e)[:100])
                    await asyncio.sleep(wait)
                else:
                    raise

    async def send(self, message: str) -> GenerateResponse:
        self._history.append(Message(role="user", content=message))
        raw = await self._send_with_retry(message)
        resp = self._to_response(raw)
        self._history.append(Message(role="assistant", content=resp.text))
        return resp

    async def send_function_response(self, name: str, response: dict) -> GenerateResponse:
        part = types.Part(
            function_response=types.FunctionResponse(name=name, response=response)
        )
        raw = await self._send_with_retry(part)
        resp = self._to_response(raw)
        self._history.append(Message(role="assistant", content=resp.text))
        return resp

    async def send_function_responses(self, responses: list[tuple[str, dict]]) -> GenerateResponse:
        """Send ALL function results in a single message with retry."""
        parts = [
            types.Part(function_response=types.FunctionResponse(name=n, response=r))
            for n, r in responses
        ]
        raw = await self._send_with_retry(parts)
        resp = self._to_response(raw)
        self._history.append(Message(role="assistant", content=resp.text))
        return resp

    def get_history(self) -> list[Message]:
        return list(self._history)
