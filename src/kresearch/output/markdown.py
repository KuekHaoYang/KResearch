"""Report post-processing — citations and file output."""

from __future__ import annotations

import re
from pathlib import Path

from kresearch.models.mind_map import Source


def ensure_citations(text: str, sources: list[Source]) -> str:
    """Verify all citation markers [N] have matching sources."""
    refs = set(map(int, re.findall(r"\[(\d+)\]", text)))
    max_ref = max(refs) if refs else 0
    if max_ref > len(sources):
        text += "\n\n> Note: Some citations reference missing sources."
    return text


def format_source_list(sources: list[Source]) -> str:
    """Format a numbered source list for the end of a report."""
    lines: list[str] = []
    seen: set[str] = set()
    idx = 1
    for s in sources:
        if s.url in seen:
            continue
        seen.add(s.url)
        title = s.title or "Untitled"
        lines.append(f"[{idx}] {title} - {s.url}")
        idx += 1
    return "\n".join(lines)


def save_report(text: str, path: str | Path) -> Path:
    """Write the final report to a file."""
    p = Path(path)
    p.write_text(text, encoding="utf-8")
    return p
