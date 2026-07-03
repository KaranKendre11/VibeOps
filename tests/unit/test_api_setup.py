"""Setup/credential-handoff API endpoints (auth validators mocked; no network)."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from vibeops.api.main import app
from vibeops.models.results import ProjectListResult, ValidationResult


def _client() -> TestClient:
    c = TestClient(app)
    c.post("/api/session")  # establish the session cookie (persisted on the client)
    return c


def test_requires_session() -> None:
    c = TestClient(app)  # no /api/session call → no cookie
    r = c.post("/api/setup/validate-openai", json={"key": "sk-x"})
    assert r.status_code == 401


def test_validate_openai_ok_stores_key_and_never_echoes_it() -> None:
    c = _client()
    with patch(
        "vibeops.api.routes_setup.validate_openai_key",
        return_value=ValidationResult(ok=True, message="ok", fingerprint="…abcd"),
    ):
        r = c.post("/api/setup/validate-openai", json={"key": "sk-secret-123"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["fingerprint"] == "…abcd"
    assert "sk-secret-123" not in r.text  # raw key must never come back


def test_validate_openai_rejects_bad_key() -> None:
    c = _client()
    with patch(
        "vibeops.api.routes_setup.validate_openai_key",
        return_value=ValidationResult(ok=False, message="Invalid OpenAI API key."),
    ):
        r = c.post("/api/setup/validate-openai", json={"key": "bad"})
    assert r.status_code == 200 and r.json()["ok"] is False


def test_projects_requires_gcp_first() -> None:
    c = _client()
    assert c.get("/api/setup/projects").status_code == 400


def test_full_setup_completes() -> None:
    c = _client()
    with patch(
        "vibeops.api.routes_setup.validate_openai_key",
        return_value=ValidationResult(ok=True, message="ok", fingerprint="…abcd"),
    ):
        c.post("/api/setup/validate-openai", json={"key": "sk-x"})
    with patch(
        "vibeops.api.routes_setup.validate_gcp_credentials",
        return_value=ValidationResult(ok=True, message="ok", fingerprint="svc"),
    ):
        c.post("/api/setup/validate-gcp", json={"sa_json": {"client_email": "svc@x.iam"}})
    with patch(
        "vibeops.api.routes_setup.list_gcp_projects",
        return_value=ProjectListResult(project_ids=["proj-1", "proj-2"]),
    ):
        r = c.get("/api/setup/projects")
    assert r.json()["project_ids"] == ["proj-1", "proj-2"]
    r = c.post(
        "/api/setup/complete",
        json={"project_id": "proj-1", "monthly_cost_cap_usd": 300.0},
    )
    assert r.json()["ok"] is True


def test_demo_entry_marks_complete() -> None:
    c = _client()
    r = c.post("/api/setup/demo")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["thread_id"]
