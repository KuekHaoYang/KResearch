"""WebSocket endpoint for real-time research streaming."""

from __future__ import annotations

import json

from starlette.websockets import WebSocket, WebSocketDisconnect

from kresearch.config import KResearchConfig
from kresearch.web.session import SessionManager


async def ws_endpoint(websocket: WebSocket) -> None:
    """Handle a WebSocket connection for one research session."""
    await websocket.accept()
    mgr: SessionManager = websocket.app.state.session_manager
    db = websocket.app.state.db
    session = None

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "data": {"message": "Invalid JSON"}})
                continue

            msg_type = msg.get("type", "")

            if msg_type == "start":
                query = msg.get("query", "").strip()
                if not query:
                    await websocket.send_json({
                        "type": "error", "data": {"message": "Query is required"},
                    })
                    continue

                # Build config with optional overrides
                overrides = msg.get("config", {})
                safe_overrides = {}
                for k, v in overrides.items():
                    if v != "" and v is not None and k in KResearchConfig.model_fields:
                        safe_overrides[k] = v
                config = KResearchConfig(**safe_overrides)

                session = mgr.create_session(websocket, config)
                await websocket.send_json({
                    "type": "session_created",
                    "data": {"session_id": session.session_id},
                })
                await session.start(query, db)

            elif msg_type == "interrupt":
                if session:
                    message = msg.get("message", "stop")
                    await session.interrupt(message)

            elif msg_type == "stop":
                if session:
                    await session.interrupt("stop")

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        if session:
            mgr.remove(session.session_id)
