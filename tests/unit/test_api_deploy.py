"""Deploy endpoints: launch contract + SSE log draining (background thread mocked/bypassed)."""
from __future__ import annotations

import queue
from unittest.mock import patch

from fastapi.testclient import TestClient

from vibeops.api.main import app
from vibeops.api.session import SESSION_COOKIE, get_store
from vibeops.graph.orchestrator import build_graph
from vibeops.models.deployment import DeploymentPhase
from vibeops.models.state import FlowStage, GraphState


def test_start_requires_session() -> None:
    c = TestClient(app)
    assert c.post("/api/deploy/start").status_code == 401


def test_start_launches_and_returns() -> None:
    c = TestClient(app)
    c.post("/api/session")
    session = get_store().get(c.cookies.get(SESSION_COOKIE))
    assert session is not None
    with patch("vibeops.api.routes_deploy._run_deploy"):  # don't run a real deploy thread
        r = c.post("/api/deploy/start")
    assert r.status_code == 200
    assert r.json()["status"] == "started"
    assert session.log_queue is not None


def test_retry_launches_in_background() -> None:
    c = TestClient(app)
    c.post("/api/session")
    session = get_store().get(c.cookies.get(SESSION_COOKIE))
    assert session is not None
    with patch("vibeops.api.routes_deploy._run_deploy"):  # don't run a real deploy thread
        r = c.post("/api/deploy/retry")
    assert r.status_code == 200
    assert r.json()["status"] == "started"
    assert session.log_queue is not None


def test_logs_streams_queue_then_final_event() -> None:
    c = TestClient(app)
    c.post("/api/session")
    session = get_store().get(c.cookies.get(SESSION_COOKIE))
    assert session is not None
    # Seed a valid finished state so the final get_state resolves.
    session.graph = build_graph()
    seed = GraphState(
        user_prompt="x", stage=FlowStage.DEPLOYMENT, deployment_phase=DeploymentPhase.SUCCEEDED
    )
    session.graph.update_state({"configurable": {"thread_id": session.thread_id}}, seed.model_dump())
    # Simulate what the background worker pushes onto the queue.
    session.log_queue = queue.Queue()
    for line in ["terraform apply...", "Apply complete!"]:
        session.log_queue.put(line)
    session.log_queue.put(None)  # sentinel

    r = c.get("/api/deploy/logs")
    assert r.status_code == 200
    assert "terraform apply..." in r.text
    assert "Apply complete!" in r.text
    assert '"done": true' in r.text
    assert '"phase": "succeeded"' in r.text
