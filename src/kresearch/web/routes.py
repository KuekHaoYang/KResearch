"""REST API routes for the Web UI."""

from __future__ import annotations

import asyncio
from pathlib import Path

from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

from kresearch.config import KResearchConfig
from kresearch.providers import PROVIDER_REGISTRY, get_provider
from kresearch.web import db as report_db
from kresearch.web.models import ConfigFieldInfo, ConfigResponse

_STATIC_DIR = Path(__file__).parent / "static"

# Widget metadata for known config fields (choices populated dynamically where needed)
_FIELD_WIDGETS: dict[str, tuple[str, list[str]]] = {
    "provider": ("select", list(PROVIDER_REGISTRY.keys())),
    "model": ("combo", []),       # populated dynamically via /api/models
    "fast_model": ("combo", []),  # populated dynamically via /api/models
    "thinking_level": ("select", ["none", "low", "medium", "high"]),
}


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
        # Determine widget and choices
        if name in _FIELD_WIDGETS:
            widget, choices = _FIELD_WIDGETS[name]
        elif is_secret:
            widget, choices = "password", []
        elif ftype == "bool":
            widget, choices = "checkbox", []
        elif ftype == "int":
            widget, choices = "number", []
        else:
            widget, choices = "text", []
        fields.append(ConfigFieldInfo(
            name=name, type=ftype, default=field_info.default,
            current="" if is_secret else val,
            is_secret=is_secret, widget=widget, choices=choices,
        ))
    return JSONResponse(ConfigResponse(fields=fields).model_dump())


async def list_models(request: Request) -> JSONResponse:
    """Fetch available models from the provider API, just like --list-models."""
    provider_name = request.query_params.get("provider", "")
    overrides: dict = {}
    if provider_name:
        overrides["provider"] = provider_name
    # Pass through API keys from query params so the provider can authenticate
    for key_field in ("gemini_api_key", "openai_api_key", "custom_api_key", "custom_api_base"):
        val = request.query_params.get(key_field, "")
        if val:
            overrides[key_field] = val
    try:
        cfg = KResearchConfig(**overrides)
        prov = get_provider(cfg)
        models = await asyncio.to_thread(prov.list_models)
        return JSONResponse([{"id": m.id, "name": m.name, "context_window": m.context_window}
                             for m in models])
    except Exception as e:
        return JSONResponse({"error": str(e)[:300]}, status_code=400)


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
    Route("/api/models", list_models),
    Route("/api/reports", list_reports),
    Route("/api/reports/{session_id}", get_report_detail),
    Route("/api/reports/{session_id}", delete_report, methods=["DELETE"]),
]
