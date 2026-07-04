"""Setup / credential-handoff endpoints — the API equivalent of the Streamlit setup screen.

Credentials are validated via ``core.auth`` and stored on the in-memory session. The real
``LLMClient`` / ``GcpContext`` are built lazily at graph-invoke time (see the graph router), not
here, so setup stays fast and side-effect-free.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from vibeops.api.deps import SessionDep
from vibeops.api.session import Session
from vibeops.core.analytics import track
from vibeops.core.auth import list_gcp_projects, validate_gcp_credentials, validate_openai_key
from vibeops.core.errors import AuthError
from vibeops.models.results import CustomImage, Network

router = APIRouter(prefix="/api/setup", tags=["setup"])


def _seed_demo_resources(session: Session) -> None:
    """Populate the simulated cloud-resource dashboard for demo mode.

    Networks + a sample custom image represent pre-existing project resources so the
    dashboard is populated the moment demo mode starts; VMs and their disks are added by
    a (simulated) demo deployment. Everything here is fake — no GCP call is ever made.
    """
    session.demo_vms = []
    session.demo_disks = []
    session.demo_networks = [
        Network(
            name="default",
            self_link=(
                "https://www.googleapis.com/compute/v1/projects/"
                "vibeops-demo/global/networks/default"
            ),
            auto_create_subnetworks=True,
        )
    ]
    session.demo_images = [
        CustomImage(
            name="vibeops-demo-base-image",
            disk_size_gb=50,
            family="vibeops-demo",
            status="READY",
            creation_timestamp="2026-06-01T09:00:00.000-07:00",
        )
    ]


class OpenAIKeyIn(BaseModel):
    key: str


class GcpCredsIn(BaseModel):
    sa_json: dict[str, Any]


class CompleteIn(BaseModel):
    project_id: str
    monthly_cost_cap_usd: float


@router.post("/validate-openai")
def validate_openai(body: OpenAIKeyIn, session: SessionDep) -> dict[str, Any]:
    result = validate_openai_key(body.key)
    if result.ok:
        session.openai_key = body.key
        session.llm_client = None  # rebuilt lazily at invoke time
    return {"ok": result.ok, "message": result.message, "fingerprint": result.fingerprint}


@router.post("/validate-gcp")
def validate_gcp(body: GcpCredsIn, session: SessionDep) -> dict[str, Any]:
    result = validate_gcp_credentials(body.sa_json)
    if result.ok:
        session.gcp_sa_json = body.sa_json
        session.gcp_context = None  # rebuilt once a project is chosen
    return {"ok": result.ok, "message": result.message, "fingerprint": result.fingerprint}


@router.get("/projects")
def projects(session: SessionDep) -> dict[str, Any]:
    if not session.gcp_sa_json:
        raise HTTPException(status_code=400, detail="Validate GCP credentials first.")
    try:
        result = list_gcp_projects(session.gcp_sa_json)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"project_ids": result.project_ids}


@router.post("/complete")
def complete(body: CompleteIn, session: SessionDep) -> dict[str, Any]:
    session.gcp_project_id = body.project_id
    session.monthly_cost_cap_usd = body.monthly_cost_cap_usd
    session.demo_mode = False
    session.setup_complete = bool(
        session.openai_key and session.gcp_sa_json and session.gcp_project_id
    )
    if session.setup_complete:
        track("setup_completed", {"demo_mode": False}, session_id=session.thread_id)
    return {"ok": session.setup_complete}


@router.post("/demo")
def demo(session: SessionDep) -> dict[str, Any]:
    """Enter credential-free demo mode: clear any creds, mark setup complete."""
    session.reset_credentials()
    session.demo_mode = True
    session.setup_complete = True
    _seed_demo_resources(session)
    track("demo_started", session_id=session.thread_id)
    return {"ok": True, "thread_id": session.thread_id}
