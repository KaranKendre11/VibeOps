"""Cloud-resource dashboard endpoints — list Compute Engine resources and delete them.

Wraps ``tools/compute``. SCOPE: Compute Engine only (instances, persistent disks, custom
images, VPC networks) — all served by the already-installed ``google.cloud.compute_v1``.
Per-resource deletes act DIRECTLY on the GCP API (outside Terraform state), which is
acceptable for this dashboard's v1.

# TODO(#16 follow-up): GCS buckets need google-cloud-storage (not installed) — add a
# ``buckets`` group here and a ``storage`` wrapper once that dependency lands.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from vibeops.api.deps import SessionDep
from vibeops.core.errors import GCPToolError
from vibeops.tools.compute import (
    delete_disk,
    delete_image,
    delete_instance,
    delete_network,
    list_custom_images,
    list_disks,
    list_networks,
    list_running_instances,
)

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.get("")
def list_inventory(session: SessionDep) -> dict[str, Any]:
    """List Compute Engine resources — simulated in demo mode, else the real GCP project.

    Returns ``instances``, ``disks``, ``images`` and ``networks``. ``available``/``instances``
    are preserved for back-compat with older clients.
    """
    if session.demo_mode:
        return {
            "available": True,
            "instances": [vm.model_dump(mode="json") for vm in session.demo_vms],
            "disks": [d.model_dump(mode="json") for d in session.demo_disks],
            "images": [img.model_dump(mode="json") for img in session.demo_images],
            "networks": [n.model_dump(mode="json") for n in session.demo_networks],
        }
    session.ensure_clients()
    ctx = session.gcp_context
    if ctx is None:
        return {"available": False, "instances": [], "disks": [], "images": [], "networks": []}
    try:
        instances = list_running_instances(ctx)
        disks = list_disks(ctx)
        images = list_custom_images(ctx)
        networks = list_networks(ctx)
    except GCPToolError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "available": True,
        "instances": [i.model_dump(mode="json") for i in instances.instances],
        "disks": [d.model_dump(mode="json") for d in disks.disks],
        "images": [img.model_dump(mode="json") for img in images.images],
        "networks": [n.model_dump(mode="json") for n in networks.networks],
    }


def _require_ctx(session: SessionDep) -> Any:
    session.ensure_clients()
    ctx = session.gcp_context
    if ctx is None:
        raise HTTPException(status_code=400, detail="No GCP credentials in session.")
    return ctx


@router.delete("/instance/{zone}/{name}")
def delete_vm(zone: str, name: str, session: SessionDep) -> dict[str, Any]:
    if session.demo_mode:
        session.demo_vms = [
            v for v in session.demo_vms if not (v.zone == zone and v.name == name)
        ]
        return {"ok": True}
    ctx = _require_ctx(session)
    try:
        delete_instance(ctx, zone, name)
    except GCPToolError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"ok": True}


@router.delete("/disk/{zone}/{name}")
def delete_pd(zone: str, name: str, session: SessionDep) -> dict[str, Any]:
    if session.demo_mode:
        session.demo_disks = [
            d for d in session.demo_disks if not (d.zone == zone and d.name == name)
        ]
        return {"ok": True}
    ctx = _require_ctx(session)
    try:
        delete_disk(ctx, zone, name)
    except GCPToolError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"ok": True}


@router.delete("/image/{name}")
def delete_img(name: str, session: SessionDep) -> dict[str, Any]:
    if session.demo_mode:
        session.demo_images = [img for img in session.demo_images if img.name != name]
        return {"ok": True}
    ctx = _require_ctx(session)
    try:
        delete_image(ctx, name)
    except GCPToolError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"ok": True}


@router.delete("/network/{name}")
def delete_net(name: str, session: SessionDep) -> dict[str, Any]:
    if session.demo_mode:
        session.demo_networks = [n for n in session.demo_networks if n.name != name]
        return {"ok": True}
    ctx = _require_ctx(session)
    try:
        delete_network(ctx, name)
    except GCPToolError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"ok": True}
