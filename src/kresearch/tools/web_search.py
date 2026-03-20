"""Web search tool using DuckDuckGo (ddgs library)."""

from __future__ import annotations

import asyncio
import logging

from kresearch.providers.types import ToolDeclaration

log = logging.getLogger(__name__)

WEB_SEARCH_DECLARATION = ToolDeclaration(
    name="web_search",
    description=(
        "Search the web using DuckDuckGo. Returns a list of results with "
        "title, URL, and snippet. Use specific, targeted queries — not vague "
        "ones. Include year for time-sensitive topics. Use quotes for exact "
        "phrases. Try multiple different queries per sub-topic."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query. Be specific and targeted.",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results to return (default 10, max 20).",
            },
        },
        "required": ["query"],
    },
)


async def handle_web_search(args: dict, **_ctx) -> dict:
    """Execute a DuckDuckGo web search with error handling."""
    query = args.get("query", "")
    if not query:
        return {"error": "Empty search query.", "results": []}
    max_results = min(args.get("max_results", 10), 20)

    def _search():
        from ddgs import DDGS
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))

    try:
        raw_results = await asyncio.to_thread(_search)
    except Exception as e:
        log.warning("Web search failed for %r: %s", query, e)
        return {"error": f"Search failed: {e}", "results": [], "query": query}

    results = [
        {
            "title": r.get("title", ""),
            "url": r.get("href", ""),
            "snippet": r.get("body", ""),
        }
        for r in raw_results
    ]
    return {"results": results, "count": len(results), "query": query}
