"""VM inventory endpoints — list running instances and delete them (wraps tools/compute)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from vibeops.api.deps import SessionDep
from vibeops.core.errors import GCPToolError
from vibeops.tools.compute import delete_instance, list_running_instances

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.get("")
def list_inventory(session: SessionDep) -> dict[str, Any]:
    """List running instances — the simulated set in demo mode, else the real GCP project."""
    if session.demo_mode:
        return {
            "available": True,
            "instances": [vm.model_dump(mode="json") for vm in session.demo_vms],
        }
    session.ensure_clients()
    ctx = session.gcp_context
    if ctx is None:
        return {"available": False, "instances": []}
    try:
        result = list_running_instances(ctx)
    except GCPToolError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "available": True,
        "instances": [i.model_dump(mode="json") for i in result.instances],
    }


@router.delete("/{zone}/{name}")
def delete_vm(zone: str, name: str, session: SessionDep) -> dict[str, Any]:
    if session.demo_mode:
        session.demo_vms = [v for v in session.demo_vms if not (v.zone == zone and v.name == name)]
        return {"ok": True}
    session.ensure_clients()
    ctx = session.gcp_context
    if ctx is None:
        raise HTTPException(status_code=400, detail="No GCP credentials in session.")
    try:
        delete_instance(ctx, zone, name)
    except GCPToolError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"ok": True}
