"""Abstract base classes for LLM providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from kresearch.providers.types import (
    GenerateResponse,
    Message,
    ModelInfo,
    ToolDeclaration,
)


class ChatSession(ABC):
    """Abstract multi-turn chat session."""

    @abstractmethod
    async def send(self, message: str) -> GenerateResponse:
        """Send a user message and get a response."""

    @abstractmethod
    async def send_function_response(
        self, name: str, response: dict
    ) -> GenerateResponse:
        """Send the result of a single function call back to the model."""

    async def send_function_responses(
        self, responses: list[tuple[str, dict]]
    ) -> GenerateResponse:
        """Send multiple function results in one message.

        Providers should override for proper batch support.
        Default: sends one at a time (less correct but functional).
        """
        result = GenerateResponse()
        for name, resp in responses:
            result = await self.send_function_response(name, resp)
        return result

    @abstractmethod
    def get_history(self) -> list[Message]:
        """Return the conversation history."""


class ProviderInterface(ABC):
    """Abstract LLM provider that any backend must implement."""

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        *,
        system_instruction: str | None = None,
        tools: list[ToolDeclaration] | None = None,
        thinking_level: str | None = None,
    ) -> GenerateResponse:
        """One-shot generation."""

    @abstractmethod
    async def generate_stream(
        self,
        messages: list[Message],
        *,
        system_instruction: str | None = None,
        tools: list[ToolDeclaration] | None = None,
        thinking_level: str | None = None,
    ) -> AsyncIterator[str]:
        """Streaming generation (yields text chunks)."""

    @abstractmethod
    async def create_chat(
        self,
        *,
        system_instruction: str | None = None,
        tools: list[ToolDeclaration] | None = None,
        thinking_level: str | None = None,
    ) -> ChatSession:
        """Create a multi-turn chat session."""

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        """List available models from the provider API."""
