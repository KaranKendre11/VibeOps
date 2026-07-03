"""Graph orchestration endpoints, exercised end-to-end via demo mode (no network)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from vibeops.api.main import app


def _demo_client() -> TestClient:
    c = TestClient(app)
    c.post("/api/session")
    c.post("/api/setup/demo")
    return c


def test_requires_session() -> None:
    c = TestClient(app)
    assert c.post("/api/graph/start", json={"prompt": "x"}).status_code == 401


def test_demo_flow_runs_to_review() -> None:
    c = _demo_client()
    r = c.post("/api/graph/start", json={"prompt": "A T4 GPU VM for Jupyter"})
    assert r.status_code == 200
    body = r.json()
    assert body["stage"] == "review"
    state = body["state"]
    assert set(state["terraform_files"]) == {"main.tf", "variables.tf", "outputs.tf"}
    assert "google_compute_instance" in state["terraform_files"]["main.tf"]
    assert state["cost_estimate"] is not None
    assert state["cost_estimate"]["monthly_usd"] > 0
    # Credentials must never appear in the serialized graph state.
    assert "sk-" not in r.text
    assert "private_key" not in r.text


def test_state_endpoint_returns_snapshot() -> None:
    c = _demo_client()
    c.post("/api/graph/start", json={"prompt": "A T4 GPU VM"})
    r = c.get("/api/graph/state")
    assert r.status_code == 200
    assert r.json()["stage"] == "review"
