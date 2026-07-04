"""Session-lifecycle endpoints.

Currently exposes a single "clear credentials" action powering the UI's explicit
"clear credentials & exit" control. It wipes every credential-derived value from the
in-memory session (keys, clients, project, setup flags) while leaving the browser's
session cookie intact, so a fresh setup can reuse the same thread. Nothing is persisted,
matching the bring-your-own-key, session-only security model in ``session.py``.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from vibeops.api.deps import SessionDep

router = APIRouter(prefix="/api/session", tags=["session"])


@router.post("/reset")
def reset_session(session: SessionDep) -> dict[str, Any]:
    """Clear all credential-derived state for this session (server-side sign-out).

    Delegates to :meth:`Session.reset_credentials`, which drops the OpenAI key, GCP
    service-account JSON, project id, constructed ``LLMClient``/``GcpContext``, and the
    ``setup_complete``/``demo_mode`` flags. The session itself (and its cookie) survives,
    so the browser can go straight back through setup without a new session.
    """
    session.reset_credentials()
    return {"ok": True}
