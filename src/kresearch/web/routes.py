"""REST API routes for the Web UI."""

from __future__ import annotations

from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

from kresearch.config import KResearchConfig
from kresearch.web import db as report_db
from kresearch.web.models import ConfigFieldInfo, ConfigResponse

_STATIC_DIR = Path(__file__).parent / "static"


async def index(request: Request) -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html", media_type="text/html")


async def health(request: Request) -> JSONResponse:
    mgr = request.app.state.session_manager
    return JSONResponse({"status": "ok", "active_sessions": mgr.active_count})


async def get_config(request: Request) -> JSONResponse:
    cfg = KResearchConfig()
    fields = []
    for name, field_info in cfg.model_fields.items():
        if name == "model_config":
            continue
        val = getattr(cfg, name, None)
        is_secret = "key" in name.lower()
        ftype = "bool" if isinstance(val, bool) else "int" if isinstance(val, int) else "str"
        fields.append(ConfigFieldInfo(
            name=name, type=ftype, default=field_info.default,
            current="********" if is_secret and val else val,
            is_secret=is_secret,
        ))
    resp = ConfigResponse(fields=fields)
    return JSONResponse(resp.model_dump())


async def list_reports(request: Request) -> JSONResponse:
    db = request.app.state.db
    reports = await report_db.list_reports(db)
    return JSONResponse([r.model_dump() for r in reports])


async def get_report_detail(request: Request) -> JSONResponse:
    db = request.app.state.db
    session_id = request.path_params["session_id"]
    report = await report_db.get_report(db, session_id)
    if not report:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(report.model_dump())


async def delete_report(request: Request) -> JSONResponse:
    db = request.app.state.db
    session_id = request.path_params["session_id"]
    deleted = await report_db.delete_report(db, session_id)
    if not deleted:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse({"deleted": True})


routes = [
    Route("/", index),
    Route("/api/health", health),
    Route("/api/config", get_config),
    Route("/api/reports", list_reports),
    Route("/api/reports/{session_id}", get_report_detail),
    Route("/api/reports/{session_id}", delete_report, methods=["DELETE"]),
]
