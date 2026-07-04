"""Deployment endpoints: launch apply/destroy in the background and stream live logs via SSE.

``terraform apply``/``destroy`` can run for minutes, so the graph invoke runs in a background
thread that forwards the runner's ``on_log`` lines into a per-session queue; ``/api/deploy/logs``
drains that queue as Server-Sent Events, then emits a final event with the outcome.
"""
from __future__ import annotations

import json
import queue
import threading
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from vibeops.api.deps import SessionDep
from vibeops.api.graph_runtime import derive_stage, get_graph, thread_config
from vibeops.api.session import Session
from vibeops.core.analytics import track
from vibeops.models.deployment import DeploymentPhase
from vibeops.models.results import RunningInstance
from vibeops.models.state import GraphState

router = APIRouter(prefix="/api/deploy", tags=["deploy"])


def _run_deploy(session: Session, updates: dict[str, Any]) -> None:
    """Background worker: apply updates + invoke the graph, forwarding runner logs to the queue."""
    q = session.log_queue
    try:
        graph = get_graph(session)
        thread = thread_config(session)
        thread["configurable"]["on_log"] = q.put  # runner emits log lines -> queue
        if updates:
            graph.update_state(thread, updates)
        graph.invoke(None, thread)
        if session.demo_mode:
            _record_demo_result(session)
    except Exception as exc:
        q.put(f"[error] {exc}")
    finally:
        q.put(None)  # sentinel: end of stream


def _launch(session: Session, updates: dict[str, Any]) -> None:
    session.log_queue = queue.Queue()
    threading.Thread(target=_run_deploy, args=(session, updates), daemon=True).start()


def _record_demo_result(session: Session) -> None:
    """Sync the session's simulated VM inventory after a demo apply/destroy."""
    try:
        values = get_graph(session).get_state(thread_config(session)).values
        state = GraphState.model_validate(values)
    except Exception:
        return
    if state.deployment_phase == DeploymentPhase.SUCCEEDED:
        spec = state.deployment_spec
        vm = RunningInstance(
            name="vibeops-demo-gpu-vm",
            zone=spec.compute.zone if spec else "us-central1-a",
            machine_type=spec.compute.machine_type if spec else "n1-standard-4",
            status="RUNNING",
            internal_ip="10.128.0.2",
            external_ip="203.0.113.42",
            gpu_summary=(
                f"{spec.compute.gpu_count}x {spec.compute.gpu_type.value}"
                if spec
                else "1x nvidia-tesla-t4"
            ),
        )
        session.demo_vms = [v for v in session.demo_vms if v.name != vm.name] + [vm]
    elif state.deployment_phase == DeploymentPhase.DESTROYED:
        session.demo_vms = []


class DeployStartIn(BaseModel):
    override_cost_cap: bool = False


def _current_graph_state(session: Session) -> GraphState | None:
    """Best-effort read of the paused GraphState; ``None`` when no checkpoint exists yet."""
    try:
        values = get_graph(session).get_state(thread_config(session)).values
    except Exception:
        return None
    if not values:
        return None
    try:
        return GraphState.model_validate(values)
    except Exception:
        return None


@router.post("/start")
def start_deploy(
    session: SessionDep,
    body: DeployStartIn | None = None,
) -> dict[str, str]:
    """Approve + launch deployment in the background. Stream /api/deploy/logs for live output.

    Enforces the monthly cost cap server-side — the check a direct API call cannot bypass: an
    over-cap plan (``cost_cap_exceeded``) is rejected with 409 unless the caller explicitly opts
    in with ``override_cost_cap``. The override is recorded on the graph state so the
    ``approval_router`` gate agrees.
    """
    override = bool(body.override_cost_cap) if body else False
    state = _current_graph_state(session)
    if state is not None and state.cost_cap_exceeded and not override:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Estimated monthly cost exceeds your cap of "
                f"${session.monthly_cost_cap_usd:,.2f}. Reduce the spec and re-estimate, "
                f"or resubmit with override to deploy anyway."
            ),
        )
    track("deploy_approved", session_id=session.thread_id)
    _launch(session, {"approved": True, "cost_cap_override": override})
    return {"status": "started"}


@router.post("/destroy")
def start_destroy(session: SessionDep) -> dict[str, str]:
    """Confirm + launch teardown in the background."""
    _launch(session, {"destroy_requested": True, "destroy_confirmed": True})
    return {"status": "started"}


@router.post("/retry")
def retry_deploy(session: SessionDep) -> dict[str, str]:
    """Retry a failed deployment in the background; stream /api/deploy/logs for live output."""
    _launch(session, {"retry_requested": True})
    return {"status": "started"}


@router.get("/logs")
def deploy_logs(session: SessionDep) -> StreamingResponse:
    q = session.log_queue

    def gen() -> Iterator[str]:
        if q is None:
            yield f"data: {json.dumps({'done': True, 'error': 'no deployment running'})}\n\n"
            return
        while True:
            line = q.get()
            if line is None:
                break
            yield f"data: {json.dumps({'log': line})}\n\n"
        payload: dict[str, Any] = {"done": True}
        try:
            new_state = GraphState.model_validate(
                get_graph(session).get_state(thread_config(session)).values
            )
            payload["stage"] = derive_stage(new_state)
            payload["phase"] = new_state.deployment_phase.value
        except Exception:
            pass
        yield f"data: {json.dumps(payload)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
