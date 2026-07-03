"""Privacy-safe funnel analytics.

Emits one JSON line per event through the (already credential-redacting) logger, and optionally
POSTs to a hosted sink when ``VIBEOPS_ANALYTICS_URL`` is set. Events carry a caller-supplied
anonymous session id and never contain credentials, project ids, or emails — so they are safe to
emit even on shared multi-tenant hosts.

Callers (the FastAPI layer) pass ``session_id`` and, for ``track_once``, the per-session ``fired``
set held on the API session. There is no Streamlit / ambient session dependency.
``track()`` must NEVER raise — analytics can't be allowed to break a deployment.
"""
from __future__ import annotations

import json
import logging
import os
import urllib.request
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger("vibeops.analytics")

_EVENT_PREFIX = "VIBEOPS_EVENT"

# Never emit these, even if a caller passes them (defense in depth on top of the session-id-only
# design and the logger's RedactingFormatter).
_BLOCKED_PROP_KEYS = frozenset(
    {
        "openai_key",
        "api_key",
        "gcp_sa_json",
        "sa_json",
        "service_account_info",
        "credentials",
        "private_key",
        "client_email",
        "email",
        "project_id",
        "gcp_project_id",
    }
)

# Process-wide fallback dedupe set for track_once when no per-session set is supplied.
_process_fired: set[str] = set()


def track(
    event: str, props: dict[str, Any] | None = None, *, session_id: str | None = None
) -> None:
    """Record a funnel event. Never raises. Emits no credentials or PII."""
    try:
        clean = {k: v for k, v in (props or {}).items() if k not in _BLOCKED_PROP_KEYS}
        payload: dict[str, Any] = {
            "event": event,
            "ts": datetime.now(UTC).isoformat(),
            "session_id": session_id or "unknown",
            **clean,
        }
        line = json.dumps(payload, default=str)
        logger.info("%s %s", _EVENT_PREFIX, line)

        url = os.environ.get("VIBEOPS_ANALYTICS_URL")
        if url:
            _post(url, line)
    except Exception:  # analytics must never break the app
        logger.debug("analytics.track failed", exc_info=True)


def track_once(
    event: str,
    props: dict[str, Any] | None = None,
    *,
    session_id: str | None = None,
    fired: set[str] | None = None,
) -> None:
    """Fire ``track`` at most once per (session, event).

    Pass ``fired`` (the API session's set) to dedupe per session; otherwise a process-wide set is
    used, keyed by session id so different sessions don't suppress each other.
    """
    try:
        target = fired if fired is not None else _process_fired
        key = f"{session_id}:{event}"
        if key in target:
            return
        target.add(key)
    except Exception:
        pass
    track(event, props, session_id=session_id)


def _post(url: str, line: str) -> None:
    try:
        req = urllib.request.Request(
            url,
            data=line.encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=1).close()
    except Exception:
        logger.debug("analytics.post failed", exc_info=True)
