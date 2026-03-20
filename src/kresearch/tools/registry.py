"""Tool registry — dynamic registration and execution of tools."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from kresearch.providers.types import ToolDeclaration


class ToolRegistry:
    """Manages tool declarations and handlers."""

    def __init__(self) -> None:
        self._handlers: dict[str, Callable] = {}
        self._declarations: list[ToolDeclaration] = []

    def register(
        self,
        name: str,
        handler: Callable,
        declaration: ToolDeclaration,
    ) -> None:
        self._handlers[name] = handler
        self._declarations.append(declaration)

    async def execute(self, name: str, args: dict, **ctx: Any) -> dict:
        handler = self._handlers.get(name)
        if not handler:
            return {"error": f"Unknown tool: {name}"}
        try:
            return await handler(args, **ctx)
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    def get_declarations(self) -> list[ToolDeclaration]:
        return list(self._declarations)

    def has(self, name: str) -> bool:
        return name in self._handlers


def create_default_registry() -> ToolRegistry:
    """Create a registry with all built-in tools."""
    from kresearch.tools.code_executor import (
        EXECUTE_PYTHON_DECLARATION,
        handle_execute_python,
    )
    from kresearch.tools.research_tools import (
        DRAFT_REPORT_DECLARATION,
        LOG_CONTRADICTION_DECLARATION,
        UPDATE_FINDINGS_DECLARATION,
        handle_draft_report,
        handle_log_contradiction,
        handle_update_findings,
    )
    from kresearch.tools.subagent_tool import (
        SPAWN_SUBAGENT_DECLARATION,
        handle_spawn_subagent,
    )
    from kresearch.tools.web_reader import (
        READ_WEBPAGE_DECLARATION,
        handle_read_webpage,
    )
    from kresearch.tools.web_search import (
        WEB_SEARCH_DECLARATION,
        handle_web_search,
    )

    registry = ToolRegistry()
    tools = [
        ("web_search", handle_web_search, WEB_SEARCH_DECLARATION),
        ("read_webpage", handle_read_webpage, READ_WEBPAGE_DECLARATION),
        ("execute_python", handle_execute_python, EXECUTE_PYTHON_DECLARATION),
        ("update_findings", handle_update_findings, UPDATE_FINDINGS_DECLARATION),
        ("log_contradiction", handle_log_contradiction, LOG_CONTRADICTION_DECLARATION),
        ("draft_report", handle_draft_report, DRAFT_REPORT_DECLARATION),
        ("spawn_subagent", handle_spawn_subagent, SPAWN_SUBAGENT_DECLARATION),
    ]
    for name, handler, decl in tools:
        registry.register(name, handler, decl)
    return registry
