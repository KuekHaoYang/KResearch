"""FastAPI application factory and entry point for kresearch-web."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from starlette.applications import Starlette
from starlette.routing import WebSocketRoute

from kresearch.config import KResearchConfig
from kresearch.web import db as report_db
from kresearch.web.routes import routes
from kresearch.web.session import SessionManager
from kresearch.web.ws import ws_endpoint


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    cfg = KResearchConfig()
    app.state.db = await report_db.init_db(cfg.web_db_path)
    app.state.session_manager = SessionManager()
    yield
    await app.state.db.close()


def create_app() -> Starlette:
    """Build the Starlette ASGI application."""
    return Starlette(
        routes=[*routes, WebSocketRoute("/ws", ws_endpoint)],
        lifespan=lifespan,
    )


def main() -> None:
    """Entry point for the ``kresearch-web`` console script."""
    import uvicorn
    cfg = KResearchConfig()
    app = create_app()
    uvicorn.run(app, host=cfg.web_host, port=cfg.web_port)


if __name__ == "__main__":
    main()
