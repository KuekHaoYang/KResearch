"""Research tools — update findings, log contradictions, draft report."""

from __future__ import annotations

import json

from kresearch.models.mind_map import Source
from kresearch.providers.types import ToolDeclaration

UPDATE_FINDINGS_DECLARATION = ToolDeclaration(
    name="update_findings",
    description=(
        "Record a research finding in the mind map. Provide the topic, "
        "content, sources (list of {url, title}), and a confidence "
        "score from 0.0 to 1.0."
    ),
    parameters={
        "type": "object",
        "properties": {
            "topic": {"type": "string", "description": "The topic/category."},
            "content": {"type": "string", "description": "The finding text."},
            "sources": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "title": {"type": "string"},
                    },
                },
                "description": "Sources for this finding.",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence 0.0-1.0.",
            },
        },
        "required": ["topic", "content", "sources", "confidence"],
    },
)

LOG_CONTRADICTION_DECLARATION = ToolDeclaration(
    name="log_contradiction",
    description=(
        "Record a contradiction between two sources. This helps "
        "track conflicting information for later resolution."
    ),
    parameters={
        "type": "object",
        "properties": {
            "topic": {"type": "string"},
            "claim_a": {"type": "string"},
            "claim_b": {"type": "string"},
            "source_a": {
                "type": "object",
                "properties": {"url": {"type": "string"}, "title": {"type": "string"}},
            },
            "source_b": {
                "type": "object",
                "properties": {"url": {"type": "string"}, "title": {"type": "string"}},
            },
        },
        "required": ["topic", "claim_a", "claim_b", "source_a", "source_b"],
    },
)

DRAFT_REPORT_DECLARATION = ToolDeclaration(
    name="draft_report",
    description=(
        "Signal that you are ready to write the final report. "
        "Returns the full mind map data. After calling this, "
        "write the complete report as your next response."
    ),
    parameters={"type": "object", "properties": {}},
)


async def handle_update_findings(args: dict, **ctx) -> dict:
    state = ctx.get("state")
    if not state:
        return {"error": "No research state available."}
    sources = [Source(url=s.get("url", ""), title=s.get("title", "")) for s in args.get("sources", [])]
    state.mind_map.add_finding(
        topic=args["topic"],
        content=args["content"],
        sources=sources,
        confidence=args.get("confidence", 0.5),
    )
    return {"status": "ok", "summary": state.mind_map.get_summary()}


async def handle_log_contradiction(args: dict, **ctx) -> dict:
    state = ctx.get("state")
    if not state:
        return {"error": "No research state available."}
    for key in ("topic", "claim_a", "claim_b", "source_a", "source_b"):
        if key not in args:
            return {"error": f"Missing required argument: {key}"}
    state.mind_map.log_contradiction(
        topic=args["topic"],
        claim_a=args["claim_a"],
        claim_b=args["claim_b"],
        source_a=Source(url=args["source_a"].get("url", ""), title=args["source_a"].get("title", "")),
        source_b=Source(url=args["source_b"].get("url", ""), title=args["source_b"].get("title", "")),
    )
    contras = state.mind_map.get_contradictions()
    return {"status": "ok", "contradictions_count": len(contras)}


async def handle_draft_report(args: dict, **ctx) -> dict:
    state = ctx.get("state")
    if not state:
        return {"error": "No research state available."}
    state.draft_requested = True
    data = state.mind_map.to_structured_data()
    return {"status": "ready", "mind_map": json.loads(json.dumps(data, default=str))}
