"""Session management — ties WebSocket, WebUI, Orchestrator, and reports together."""

from __future__ import annotations

import asyncio
import json
import time
import uuid

import aiosqlite
from starlette.websockets import WebSocket

from kresearch.config import KResearchConfig
from kresearch.orchestrator import Orchestrator
from kresearch.providers import get_provider
from kresearch.tools.registry import create_default_registry
from kresearch.web import db as report_db
from kresearch.web.webui import WebUI


class ResearchSession:
    """One research run: WebSocket + WebUI + Orchestrator task."""

    def __init__(self, session_id: str, ws: WebSocket, config: KResearchConfig) -> None:
        self.session_id = session_id
        self.ws = ws
        self.config = config
        self.webui = WebUI(ws, session_id)
        self.task: asyncio.Task | None = None
        self._start_time = 0.0
        self.query = ""

    async def start(self, query: str, db: aiosqlite.Connection) -> None:
        self.query = query
        self._start_time = time.monotonic()
        provider = get_provider(self.config)
        registry = create_default_registry()
        orchestrator = Orchestrator(
            self.config, provider, registry, self.webui,
            input_queue=self.webui.input_queue,
        )
        self.task = asyncio.create_task(self._run(orchestrator, query, db))

    async def _run(self, orchestrator: Orchestrator, query: str,
                   db: aiosqlite.Connection) -> None:
        try:
            report = await orchestrator.run(query)
            elapsed = time.monotonic() - self._start_time
            state = orchestrator.last_state
            await self.webui.show_report(report)
            await report_db.save_report(
                db, self.session_id, self.query, report,
                config_json=json.dumps({"provider": self.config.provider, "model": self.config.model}),
                source_count=state.mind_map.source_count() if state else 0,
                iteration_count=state.iteration if state else 0,
                duration_seconds=elapsed,
            )
        except asyncio.CancelledError:
            await self.webui._send("error", {"message": "Research cancelled"})
        except Exception as e:
            await self.webui._send("error", {"message": str(e)[:500]})
        finally:
            await self.webui.stop()

    async def interrupt(self, message: str) -> None:
        await self.webui.input_queue.put(message)

    def cancel(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()


class SessionManager:
    """Tracks active research sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, ResearchSession] = {}

    def create_session(self, ws: WebSocket, config: KResearchConfig) -> ResearchSession:
        session_id = uuid.uuid4().hex[:12]
        session = ResearchSession(session_id, ws, config)
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> ResearchSession | None:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session:
            session.cancel()

    @property
    def active_count(self) -> int:
        return len(self._sessions)
