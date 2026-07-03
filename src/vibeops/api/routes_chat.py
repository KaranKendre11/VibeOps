"""Requirement-conversation chat endpoint with Server-Sent-Events token streaming.

Streams the assistant's tokens as they arrive, then (server-side, once the stream ends) records
the turn, decides whether to proceed, updates the graph, and advances if confirmed. Sync ``def`` so
FastAPI threadpools the blocking LLM call.
"""
from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from vibeops.agents.requirement import build_conversation_messages_with_context
from vibeops.api.deps import SessionDep
from vibeops.api.graph_runtime import derive_stage, get_graph, thread_config
from vibeops.models.conversation import RequirementPhase
from vibeops.models.state import GraphState
from vibeops.services.conversation import evaluate_turn

router = APIRouter(prefix="/api/chat", tags=["chat"])


class TurnIn(BaseModel):
    reply: str


def _sse(obj: dict[str, Any]) -> str:
    return f"data: {json.dumps(obj)}\n\n"


@router.post("/turn")
def chat_turn(body: TurnIn, session: SessionDep) -> StreamingResponse:
    graph = get_graph(session)
    thread = thread_config(session)
    values = graph.get_state(thread).values
    state = GraphState.model_validate(values) if values else GraphState(user_prompt="")
    conversation = state.conversation
    llm = session.llm_client
    messages = build_conversation_messages_with_context(
        conversation, body.reply, state.extracted_intent
    )

    def gen() -> Iterator[str]:
        tokens: list[str] = []
        if llm is not None:
            for tok in llm.stream_text(messages, temperature=0.7):
                tokens.append(tok)
                yield _sse({"token": tok})
        else:
            tokens.append("[[PROCEED]]")
        response = "".join(tokens)

        result = evaluate_turn(conversation, body.reply, response)
        phase = (
            RequirementPhase.RESUMING_CONFIRMATION
            if result.proceed
            else RequirementPhase.ASKING
        )
        graph.update_state(
            thread,
            {"conversation": result.new_conversation, "requirement_phase": phase.value},
        )
        if result.proceed:
            graph.invoke(None, thread)

        new_state = GraphState.model_validate(graph.get_state(thread).values)
        yield _sse(
            {
                "done": True,
                "proceed": result.proceed,
                "message": result.cleaned_response,
                "stage": derive_stage(new_state),
            }
        )

    return StreamingResponse(gen(), media_type="text/event-stream")
