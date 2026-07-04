"""Review endpoints: HCL edit + cost re-estimate update state WITHOUT advancing the graph."""
from __future__ import annotations

from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient

from vibeops.api.main import app
from vibeops.api.session import SESSION_COOKIE, get_store
from vibeops.graph.orchestrator import build_graph
from vibeops.models.state import FlowStage, GraphState


def _review_client() -> TestClient:
    c = TestClient(app)
    c.post("/api/session")
    session = get_store().get(c.cookies.get(SESSION_COOKIE))
    assert session is not None
    session.graph = build_graph()
    seed = GraphState(
        user_prompt="x",
        stage=FlowStage.AWAITING_APPROVAL,
        terraform_dir="/tmp/vibeops-x",
        terraform_files={"main.tf": "resource x {}", "variables.tf": "v", "outputs.tf": "o"},
    )
    session.graph.update_state(
        {"configurable": {"thread_id": session.thread_id}}, seed.model_dump()
    )
    return c


def test_edit_requires_review_in_progress() -> None:
    c = TestClient(app)
    c.post("/api/session")
    r = c.post("/api/review/edit", json={"filename": "main.tf", "content": "x"})
    assert r.status_code == 409


def test_edit_saves_valid_change_and_stays_in_review() -> None:
    c = _review_client()

    def fake_edit(state: GraphState, filename: str, content: str) -> tuple[GraphState, None]:
        return (
            state.model_copy(update={"terraform_files": {**state.terraform_files, filename: content}}),
            None,
        )

    with patch("vibeops.api.routes_review.apply_user_edit", side_effect=fake_edit):
        r = c.post("/api/review/edit", json={"filename": "main.tf", "content": "resource updated {}"})
    assert r.status_code == 200
    body = r.json()
    assert body["stage"] == "review"
    assert body["state"]["terraform_files"]["main.tf"] == "resource updated {}"


def test_edit_rejects_invalid() -> None:
    c = _review_client()
    with patch(
        "vibeops.api.routes_review.apply_user_edit",
        return_value=(None, "Validation failed: boom"),
    ):
        r = c.post("/api/review/edit", json={"filename": "main.tf", "content": "bad"})
    assert r.status_code == 422


def test_reestimate_updates_cost() -> None:
    c = _review_client()
    update: dict[str, Any] = {
        "cost_estimate": {
            "monthly_usd": 200.0,
            "hourly_usd": 0.27,
            "source": "price_table",
            "confidence": "low",
            "breakdown": [],
            "notes": [],
        },
        "cost_estimate_stale": False,
        "cost_cap_exceeded": False,
    }
    with patch("vibeops.api.routes_review.reestimate_cost", return_value=update):
        r = c.post("/api/review/reestimate")
    assert r.status_code == 200
    assert r.json()["state"]["cost_estimate"]["monthly_usd"] == 200.0
