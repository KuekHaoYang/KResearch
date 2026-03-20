"""Provider-agnostic message and response types."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Message(BaseModel):
    """A single chat message."""

    role: str  # "user", "assistant", "system", "function"
    content: str = ""


class FunctionCall(BaseModel):
    """A function call requested by the model."""

    name: str
    args: dict = Field(default_factory=dict)


class TokenUsageInfo(BaseModel):
    """Token usage statistics from one API call."""

    input_tokens: int = 0
    output_tokens: int = 0


class GenerateResponse(BaseModel):
    """Unified response from any provider."""

    text: str = ""
    function_calls: list[FunctionCall] = Field(default_factory=list)
    thinking: str = ""
    usage: TokenUsageInfo = Field(default_factory=TokenUsageInfo)
    raw: dict = Field(default_factory=dict)


class ModelInfo(BaseModel):
    """Metadata about an available model."""

    id: str
    name: str = ""
    context_window: int = 0


class ToolDeclaration(BaseModel):
    """Provider-agnostic tool/function declaration."""

    name: str
    description: str
    parameters: dict = Field(default_factory=dict)  # JSON Schema
