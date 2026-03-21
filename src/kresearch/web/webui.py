"""WebUI — sends research events over WebSocket instead of printing to terminal."""

from __future__ import annotations

import asyncio
import re
from starlette.websockets import WebSocket

from kresearch.output.console import _summarize_result
from kresearch.web.models import WSEvent


def _strip_rich(text: str) -> str:
    """Remove Rich markup tags like [bold], [dim], [/dim], etc."""
    return re.sub(r"\[/?[a-z_ ]+\]", "", text)


class WebUI:
    """UIProtocol implementation that streams JSON events over WebSocket."""

    def __init__(self, ws: WebSocket, session_id: str) -> None:
        self._ws = ws
        self._session_id = session_id
        self.input_queue: asyncio.Queue[str] = asyncio.Queue()

    async def _send(self, event_type: str, data: dict | None = None) -> None:
        evt = WSEvent(type=event_type, data=data or {}, session_id=self._session_id)
        try:
            await self._ws.send_json(evt.model_dump())
        except Exception:
            pass  # WebSocket closed

    async def start_research(self, query: str) -> None:
        await self._send("start_research", {"query": query})

    async def log_action(self, tool: str, desc: str, status: str = "done",
                         elapsed: float | None = None) -> None:
        await self._send("action", {
            "tool": tool, "description": _strip_rich(desc),
            "status": status, "elapsed": elapsed,
        })

    async def log_thinking(self, text: str) -> None:
        if not text or len(text.strip()) < 5:
            return
        snippet = text.strip()
        if len(snippet) > 500:
            snippet = snippet[:497] + "..."
        await self._send("thinking", {"text": snippet})

    async def log_result_summary(self, tool: str, result: dict) -> None:
        summary = _summarize_result(tool, result)
        if summary:
            await self._send("result_summary", {"tool": tool, "summary": _strip_rich(summary)})

    async def update_stats(self, iteration: int, sources: int, tokens: int) -> None:
        await self._send("stats", {
            "iteration": iteration, "sources": sources, "tokens": tokens,
        })

    async def show_report(self, text: str) -> None:
        await self._send("report", {"markdown": text})

    async def show_total_time(self, elapsed: float, state: object) -> None:
        mins, secs = int(elapsed // 60), int(elapsed % 60)
        t = state.token_usage.input_tokens + state.token_usage.output_tokens  # type: ignore[attr-defined]
        await self._send("total_time", {
            "elapsed": elapsed, "time_str": f"{mins}m {secs}s" if mins else f"{secs}s",
            "sources": state.mind_map.source_count(),  # type: ignore[attr-defined]
            "iterations": state.iteration,  # type: ignore[attr-defined]
            "tokens": t,
        })

    async def stop(self) -> None:
        await self._send("stopped")

    async def print(self, msg: str, **kw: object) -> None:
        await self._send("log", {"message": _strip_rich(msg)})
