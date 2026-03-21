"""Pydantic models for WebSocket events and REST responses."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class WSEvent(BaseModel):
    """Server → client WebSocket message envelope."""

    type: str
    data: dict[str, Any] = Field(default_factory=dict)
    session_id: str = ""
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class StartResearchRequest(BaseModel):
    """Client → server: begin a research session."""

    query: str
    config: dict[str, Any] = Field(default_factory=dict)


class ConfigFieldInfo(BaseModel):
    """Metadata for one config field, used by the settings form."""

    name: str
    type: str  # "str", "int", "bool"
    default: Any
    current: Any
    is_secret: bool = False
    widget: str = "text"  # "text", "password", "number", "select", "combo", "checkbox"
    choices: list[str] = Field(default_factory=list)


class ConfigResponse(BaseModel):
    """All config fields for the settings form."""

    fields: list[ConfigFieldInfo]


class ReportSummary(BaseModel):
    """List item for past reports."""

    session_id: str
    query: str
    source_count: int = 0
    iteration_count: int = 0
    duration_seconds: float = 0.0
    created_at: str = ""


class ReportDetail(ReportSummary):
    """Full past report with markdown content."""

    report: str = ""
    config_json: str = "{}"
