"""Smoke tests for the FastAPI app skeleton (health, config, session cookie)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from vibeops.api.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_config_exposes_nonsensitive_defaults() -> None:
    r = client.get("/api/config")
    assert r.status_code == 200
    body = r.json()
    assert "default_model" in body
    assert "default_cost_cap_usd" in body


def test_create_session_sets_httponly_cookie() -> None:
    r = client.post("/api/session")
    assert r.status_code == 200
    assert "thread_id" in r.json()
    set_cookie = r.headers.get("set-cookie", "")
    assert "vibeops_session=" in set_cookie
    assert "httponly" in set_cookie.lower()
