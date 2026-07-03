"""In-process session store for the FastAPI layer.

This holds, in server MEMORY ONLY, the per-browser-session credentials and the constructed
``LLMClient`` / ``GcpContext`` — exactly the role ``st.session_state`` plays today. Nothing is
written to disk, so the "credentials are session-only and vanish when the tab closes / the process
restarts" property that protects shared multi-tenant hosts (HF Spaces, etc.) is preserved without
any external store. Sessions are keyed by an opaque id delivered to the browser in an httpOnly
cookie.

Deliberately NOT Redis/DB: VibeOps is a single-container app, so a process-local dict is the correct
scale and keeps the bring-your-own-key security model simple.
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from vibeops.config import AppConfig
from vibeops.core.gcp_context import GcpContext
from vibeops.core.llm import LLMClient

SESSION_COOKIE = "vibeops_session"


@dataclass
class Session:
    """Per-browser-session server state (in memory only; never persisted)."""

    id: str
    thread_id: str
    llm_client: LLMClient | None = None
    gcp_context: GcpContext | None = None
    graph: Any = None  # per-session compiled LangGraph (holds the MemorySaver checkpoint)
    log_queue: Any = None  # queue.Queue for streaming live deploy/destroy logs over SSE
    demo_vms: list[Any] = field(default_factory=list)  # simulated VM inventory for demo mode
    openai_key: str | None = None
    gcp_sa_json: dict[str, Any] | None = None
    gcp_project_id: str | None = None
    monthly_cost_cap_usd: float = field(default_factory=lambda: AppConfig().default_cost_cap_usd)
    demo_mode: bool = False
    setup_complete: bool = False
    analytics_fired: set[str] = field(default_factory=set)

    def ensure_clients(self) -> None:
        """Build the LLM/GCP clients from stored credentials when missing.

        Mirrors ``ui/chat._ensure_clients`` — only constructs when the creds are present.
        """
        if self.llm_client is None and self.openai_key:
            self.llm_client = LLMClient(api_key=self.openai_key)
        if self.gcp_context is None and self.gcp_sa_json and self.gcp_project_id:
            self.gcp_context = GcpContext(
                service_account_info=self.gcp_sa_json, project_id=self.gcp_project_id
            )

    def reset_credentials(self) -> None:
        """Clear all credential-derived state (the 'Reconfigure' / demo-entry action)."""
        self.llm_client = None
        self.gcp_context = None
        self.openai_key = None
        self.gcp_sa_json = None
        self.gcp_project_id = None
        self.setup_complete = False
        self.demo_mode = False


class SessionStore:
    """Thread-safe, in-memory session registry. No disk, no external store."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()

    def create(self) -> Session:
        session = Session(id=uuid.uuid4().hex, thread_id=uuid.uuid4().hex)
        with self._lock:
            self._sessions[session.id] = session
        return session

    def get(self, session_id: str | None) -> Session | None:
        if not session_id:
            return None
        with self._lock:
            return self._sessions.get(session_id)

    def delete(self, session_id: str | None) -> None:
        if not session_id:
            return
        with self._lock:
            self._sessions.pop(session_id, None)


# One process (single-container deploy) → a module-level singleton store.
_STORE = SessionStore()


def get_store() -> SessionStore:
    return _STORE
