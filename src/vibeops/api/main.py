"""FastAPI application entry point.

Serves the JSON/SSE API under ``/api`` and the built React bundle (production). This replaced the
retired Streamlit ``app.py`` as the app's single entry point.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from vibeops.api.routes_chat import router as chat_router
from vibeops.api.routes_deploy import router as deploy_router
from vibeops.api.routes_graph import router as graph_router
from vibeops.api.routes_inventory import router as inventory_router
from vibeops.api.routes_review import router as review_router
from vibeops.api.routes_setup import router as setup_router
from vibeops.api.session import SESSION_COOKIE, get_store
from vibeops.config import AppConfig
from vibeops.core.logging import configure_logging

_config = AppConfig()
configure_logging(_config.log_level)

app = FastAPI(title="VibeOps API")
app.include_router(chat_router)
app.include_router(deploy_router)
app.include_router(graph_router)
app.include_router(inventory_router)
app.include_router(review_router)
app.include_router(setup_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/config")
def config() -> dict[str, object]:
    """Public, non-sensitive defaults the frontend needs at boot."""
    return {
        "default_model": _config.default_model,
        "default_cost_cap_usd": _config.default_cost_cap_usd,
    }


def _https_context(request: Request) -> bool:
    """True when the app is served over HTTPS (e.g. on HF Spaces, behind a proxy).

    HF Spaces terminate TLS at a proxy, so the app itself sees http; trust the
    ``X-Forwarded-Proto`` header and the HF ``SPACE_ID`` env var as signals.
    """
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return proto == "https" or bool(os.getenv("SPACE_ID"))


@app.post("/api/session")
def create_session(request: Request) -> JSONResponse:
    """Start a session: allocate server-side state and set the httpOnly session cookie.

    On HTTPS (HF Spaces embeds the app in a cross-site iframe) the cookie must be
    ``SameSite=None; Secure`` or the browser won't send it back on API calls made
    from inside the iframe. Locally (http://localhost) we fall back to ``Lax`` since
    ``Secure`` cookies are never stored over plain HTTP.
    """
    session = get_store().create()
    resp = JSONResponse({"thread_id": session.thread_id})
    secure = _https_context(request)
    resp.set_cookie(
        SESSION_COOKIE,
        session.id,
        httponly=True,
        samesite="none" if secure else "lax",
        secure=secure,
    )
    return resp


# Serve the built React SPA (production). Mounted LAST so the /api routes above take precedence.
# Skipped when the bundle isn't built (backend tests, or before `npm run build`), so the API can
# always boot standalone.
_FRONTEND_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")

