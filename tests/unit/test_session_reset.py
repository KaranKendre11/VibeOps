"""POST /api/session/reset: clears credential-derived state, keeps the session cookie."""
from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from vibeops.api.main import app
from vibeops.api.session import SESSION_COOKIE, get_store


def test_reset_requires_session() -> None:
    c = TestClient(app)
    assert c.post("/api/session/reset").status_code == 401


def test_reset_clears_all_credential_state() -> None:
    c = TestClient(app)
    c.post("/api/session")
    session = get_store().get(c.cookies.get(SESSION_COOKIE))
    assert session is not None

    # Seed credential-derived state as if a real setup (or demo) had run.
    session.openai_key = "sk-test"
    session.gcp_sa_json = {"type": "service_account"}
    session.gcp_project_id = "proj-123"
    session.setup_complete = True
    session.demo_mode = True
    session.llm_client = MagicMock()
    session.gcp_context = MagicMock()

    r = c.post("/api/session/reset")
    assert r.status_code == 200
    assert r.json() == {"ok": True}

    # Every credential-derived value is wiped.
    assert session.openai_key is None
    assert session.gcp_sa_json is None
    assert session.gcp_project_id is None
    assert session.llm_client is None
    assert session.gcp_context is None
    assert session.setup_complete is False
    assert session.demo_mode is False


def test_reset_keeps_session_resolvable() -> None:
    c = TestClient(app)
    c.post("/api/session")
    sid = c.cookies.get(SESSION_COOKIE)
    session = get_store().get(sid)
    assert session is not None

    r = c.post("/api/session/reset")
    assert r.status_code == 200

    # The session (and its cookie) survive the reset, so setup can be redone in place.
    assert get_store().get(sid) is session
