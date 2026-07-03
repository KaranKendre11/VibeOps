"""Graph orchestration endpoints — start a flow, resume from an interrupt, read state.

Wraps the existing LangGraph ``build_graph()``. The per-session compiled graph (with its
``MemorySaver`` checkpointer) lives on the Session so state survives across requests, exactly as
``st.session_state['graph']`` did. Endpoints are sync ``def`` so FastAPI runs them in a threadpool,
keeping the (potentially slow, blocking) LLM / GCP / terraform work off the event loop.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from vibeops.api.deps import SessionDep
from vibeops.api.graph_runtime import get_graph, snapshot, thread_config
from vibeops.core.analytics import track
from vibeops.models.state import GraphState

router = APIRouter(prefix="/api/graph", tags=["graph"])


class StartIn(BaseModel):
    prompt: str


class ResumeIn(BaseModel):
    updates: dict[str, Any] = Field(default_factory=dict)
    as_node: str | None = None


@router.post("/start")
def start(body: StartIn, session: SessionDep) -> dict[str, Any]:
    graph = get_graph(session)
    thread = thread_config(session)
    track("requirement_submitted", {"demo_mode": session.demo_mode}, session_id=session.thread_id)
    graph.invoke(GraphState(user_prompt=body.prompt).model_dump(), thread)
    return snapshot(graph, thread)


@router.get("/state")
def state(session: SessionDep) -> dict[str, Any]:
    graph = get_graph(session)
    return snapshot(graph, thread_config(session))


@router.post("/resume")
def resume(body: ResumeIn, session: SessionDep) -> dict[str, Any]:
    graph = get_graph(session)
    thread = thread_config(session)
    if body.updates:
        if body.as_node:
            graph.update_state(thread, body.updates, as_node=body.as_node)
        else:
            graph.update_state(thread, body.updates)
    graph.invoke(None, thread)
    return snapshot(graph, thread)
