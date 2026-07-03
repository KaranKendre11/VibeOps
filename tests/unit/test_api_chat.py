"""Chat SSE endpoint: token streaming + turn evaluation (LLM mocked; no network)."""
from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from vibeops.api.main import app
from vibeops.api.session import SESSION_COOKIE, get_store
from vibeops.graph.orchestrator import build_graph
from vibeops.models.conversation import RequirementPhase
from vibeops.models.state import GraphState


def test_requires_session() -> None:
    c = TestClient(app)
    assert c.post("/api/chat/turn", json={"reply": "hi"}).status_code == 401


def test_streams_tokens_and_stays_in_chat_when_not_proceeding() -> None:
    c = TestClient(app)
    c.post("/api/session")
    session = get_store().get(c.cookies.get(SESSION_COOKIE))
    assert session is not None
    fake = MagicMock()
    fake.stream_text.return_value = iter(["How much ", "disk ", "do you need?"])
    session.openai_key = "sk-test"
    session.llm_client = fake  # injected; ensure_clients() won't rebuild it

    # Seed a valid "asking" base checkpoint (mirrors what /api/graph/start creates).
    session.graph = build_graph()
    seed = GraphState(user_prompt="run jupyter", requirement_phase=RequirementPhase.ASKING)
    session.graph.update_state(
        {"configurable": {"thread_id": session.thread_id}}, seed.model_dump()
    )

    r = c.post("/api/chat/turn", json={"reply": "I want a gpu box"})
    assert r.status_code == 200
    text = r.text
    assert "How much" in text and "do you need?" in text  # tokens streamed
    assert '"done": true' in text
    assert '"proceed": false' in text  # no [[PROCEED]] in the response
    assert '"stage": "chat"' in text  # stays in the conversation
