"""FastAPI dependencies shared across routers."""
from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException

from vibeops.api.session import SESSION_COOKIE, Session, get_store


def require_session(session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> Session:
    """Resolve the current session from the httpOnly cookie, or 401 if none exists."""
    session = get_store().get(session_id)
    if session is None:
        raise HTTPException(status_code=401, detail="No active session; POST /api/session first.")
    return session


SessionDep = Annotated[Session, Depends(require_session)]
