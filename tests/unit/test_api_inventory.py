"""VM inventory endpoints (GCP tool calls mocked; no network)."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from vibeops.api.main import app
from vibeops.api.session import SESSION_COOKIE, get_store
from vibeops.models.results import InstancesResult, RunningInstance


def _client() -> TestClient:
    c = TestClient(app)
    c.post("/api/session")
    return c


def test_list_without_credentials_is_unavailable() -> None:
    r = _client().get("/api/inventory")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is False
    assert body["instances"] == []


def test_list_with_context_returns_instances() -> None:
    c = _client()
    session = get_store().get(c.cookies.get(SESSION_COOKIE))
    assert session is not None
    session.gcp_context = object()  # non-None so ensure_clients() leaves it alone
    inst = RunningInstance(
        name="vm-1",
        zone="us-central1-a",
        machine_type="n1-standard-4",
        status="RUNNING",
        gpu_summary="1x nvidia-tesla-t4",
    )
    with patch(
        "vibeops.api.routes_inventory.list_running_instances",
        return_value=InstancesResult(instances=[inst]),
    ):
        r = c.get("/api/inventory")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["instances"][0]["name"] == "vm-1"
    assert body["instances"][0]["gpu_summary"] == "1x nvidia-tesla-t4"


def test_delete_requires_credentials() -> None:
    assert _client().delete("/api/inventory/us-central1-a/vm-1").status_code == 400


def test_delete_with_context_calls_tool() -> None:
    c = _client()
    session = get_store().get(c.cookies.get(SESSION_COOKIE))
    assert session is not None
    session.gcp_context = object()
    with patch("vibeops.api.routes_inventory.delete_instance") as mock_delete:
        r = c.delete("/api/inventory/us-central1-a/vm-1")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    mock_delete.assert_called_once()


def test_demo_inventory_returns_simulated_vms() -> None:
    c = _client()
    session = get_store().get(c.cookies.get(SESSION_COOKIE))
    assert session is not None
    session.demo_mode = True
    session.demo_vms = [
        RunningInstance(
            name="vibeops-demo-gpu-vm",
            zone="us-central1-a",
            machine_type="n1-standard-4",
            status="RUNNING",
            gpu_summary="1x nvidia-tesla-t4",
        )
    ]
    r = c.get("/api/inventory")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["instances"][0]["name"] == "vibeops-demo-gpu-vm"


def test_demo_delete_removes_simulated_vm() -> None:
    c = _client()
    session = get_store().get(c.cookies.get(SESSION_COOKIE))
    assert session is not None
    session.demo_mode = True
    session.demo_vms = [
        RunningInstance(
            name="vibeops-demo-gpu-vm",
            zone="us-central1-a",
            machine_type="n1-standard-4",
            status="RUNNING",
        )
    ]
    r = c.delete("/api/inventory/us-central1-a/vibeops-demo-gpu-vm")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert session.demo_vms == []
