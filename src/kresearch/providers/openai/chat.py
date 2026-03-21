"""OpenAI chat session with retry logic for rate limits."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from kresearch.providers.base import ChatSession
from kresearch.providers.types import (
    FunctionCall, GenerateResponse, Message, TokenUsageInfo,
)

log = logging.getLogger(__name__)
MAX_RETRIES = 5


class OpenaiChatSession(ChatSession):
    """Multi-turn chat managing OpenAI message history with retry on transient errors."""

    def __init__(self, client: Any, model: str,
                 system_instruction: str | None = None,
                 tools: list[dict] | None = None) -> None:
        self._client = client
        self._model = model
        self._tools = tools
        self._messages: list[dict] = []
        self._history: list[Message] = []
        if system_instruction:
            self._messages.append({"role": "system", "content": system_instruction})

    async def _call(self) -> Any:
        """Call the API with exponential backoff on transient errors."""
        for attempt in range(MAX_RETRIES):
            try:
                kwargs: dict[str, Any] = {
                    "model": self._model, "messages": self._messages,
                }
                if self._tools:
                    kwargs["tools"] = self._tools
                return await self._client.chat.completions.create(**kwargs)
            except Exception as e:
                err = str(e).lower()
                retryable = "429" in err or "500" in err or "503" in err
                if retryable and attempt < MAX_RETRIES - 1:
                    wait = 2 ** attempt + 1
                    log.warning("API error (attempt %d/%d), retrying in %ds: %s",
                                attempt + 1, MAX_RETRIES, wait, str(e)[:100])
                    await asyncio.sleep(wait)
                else:
                    raise

    @staticmethod
    def _parse(raw: Any) -> GenerateResponse:
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

    async def send(self, message: str) -> GenerateResponse:
        self._messages.append({"role": "user", "content": message})
        self._history.append(Message(role="user", content=message))
        raw = await self._call()
        resp = self._parse(raw)
        # Store the raw assistant message (including tool_calls) for history
        assistant_msg = raw.choices[0].message if raw.choices else None
        self._append_assistant(assistant_msg, resp)
        return resp

    def _append_assistant(self, raw_msg: Any, resp: GenerateResponse) -> None:
        """Append the assistant message to _messages in the format OpenAI expects."""
        msg: dict[str, Any] = {"role": "assistant", "content": resp.text or None}
        if raw_msg and raw_msg.tool_calls:
            msg["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in raw_msg.tool_calls
            ]
        self._messages.append(msg)
        self._history.append(Message(role="assistant", content=resp.text))
        # Stash raw tool_calls for send_function_response(s) to reference
        self._last_tool_calls = raw_msg.tool_calls if raw_msg and raw_msg.tool_calls else []

    async def send_function_response(self, name: str, response: dict) -> GenerateResponse:
        # Find the matching tool_call_id
        tc_id = self._find_tool_call_id(name)
        self._messages.append({
            "role": "tool", "tool_call_id": tc_id, "content": json.dumps(response),
        })
        raw = await self._call()
        resp = self._parse(raw)
        assistant_msg = raw.choices[0].message if raw.choices else None
        self._append_assistant(assistant_msg, resp)
        return resp

    async def send_function_responses(self, responses: list[tuple[str, dict]]) -> GenerateResponse:
        """Send all tool results as separate role=tool messages, then call the API once."""
        for name, response in responses:
            tc_id = self._find_tool_call_id(name)
            self._messages.append({
                "role": "tool", "tool_call_id": tc_id, "content": json.dumps(response),
            })
        raw = await self._call()
        resp = self._parse(raw)
        assistant_msg = raw.choices[0].message if raw.choices else None
        self._append_assistant(assistant_msg, resp)
        return resp

    def _find_tool_call_id(self, name: str) -> str:
        """Find the tool_call_id for a given function name from the last assistant message."""
        for tc in self._last_tool_calls:
            if tc.function.name == name:
                tc_id = tc.id
                # Remove from list so duplicate names are matched in order
                self._last_tool_calls = [t for t in self._last_tool_calls if t.id != tc_id]
                return tc_id
        return f"call_{name}"

    def get_history(self) -> list[Message]:
        return list(self._history)
