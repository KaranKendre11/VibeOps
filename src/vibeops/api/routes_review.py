"""Review-screen endpoints: validate/save HCL edits and re-estimate cost.

Crucially these ``update_state`` WITHOUT invoking the graph, so the flow stays paused at the
``review`` interrupt. (Resuming with anything other than ``approved=True`` hits ``approval_router``,
which fails closed and cancels — so edits must not go through /api/graph/resume.)
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from vibeops.api.deps import SessionDep
from vibeops.api.graph_runtime import get_graph, snapshot, thread_config
from vibeops.api.session import Session
from vibeops.models.state import GraphState
from vibeops.services.review import apply_user_edit, reestimate_cost

router = APIRouter(prefix="/api/review", tags=["review"])


class EditIn(BaseModel):
    filename: str
    content: str


def _current_state(session: Session) -> tuple[Any, dict[str, Any], GraphState]:
    graph = get_graph(session)
    thread = thread_config(session)
    values = graph.get_state(thread).values
    if not values:
        raise HTTPException(status_code=409, detail="No review in progress.")
    return graph, thread, GraphState.model_validate(values)


@router.post("/edit")
def edit(body: EditIn, session: SessionDep) -> dict[str, Any]:
    graph, thread, state = _current_state(session)
    new_state, err = apply_user_edit(state, body.filename, body.content)
    if err:
        raise HTTPException(status_code=422, detail=err)
    graph.update_state(
        thread,
        {"terraform_files": new_state.terraform_files, "cost_estimate_stale": True},
    )
    return snapshot(graph, thread)


@router.post("/reestimate")
def reestimate(session: SessionDep) -> dict[str, Any]:
    graph, thread, state = _current_state(session)
    session.ensure_clients()
    update = reestimate_cost(state, session.gcp_context, session.monthly_cost_cap_usd)
    if update is None:
        raise HTTPException(status_code=409, detail="Missing terraform directory or spec.")
    graph.update_state(thread, update)
    return snapshot(graph, thread)
