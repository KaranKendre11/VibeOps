"""Cloud-resource dashboard endpoints (GCP tool calls mocked; no network)."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from vibeops.api.main import app
from vibeops.api.session import SESSION_COOKIE, get_store
from vibeops.models.results import (
    CustomImage,
    CustomImagesResult,
    Disk,
    DisksResult,
    InstancesResult,
    Network,
    NetworksResult,
    RunningInstance,
)


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
    assert body["disks"] == []
    assert body["images"] == []
    assert body["networks"] == []


def test_list_with_context_returns_all_resource_groups() -> None:
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
        monthly_cost_usd=411.5,
    )
    disk = Disk(name="disk-1", zone="us-central1-a", size_gb=100, type="pd-ssd", monthly_cost_usd=17.0)
    image = CustomImage(name="img-1", disk_size_gb=50, family="fam", status="READY")
    net = Network(name="default", self_link="", auto_create_subnetworks=True)
    with (
        patch(
            "vibeops.api.routes_inventory.list_running_instances",
            return_value=InstancesResult(instances=[inst]),
        ),
        patch(
            "vibeops.api.routes_inventory.list_disks",
            return_value=DisksResult(disks=[disk]),
        ),
        patch(
            "vibeops.api.routes_inventory.list_custom_images",
            return_value=CustomImagesResult(images=[image]),
        ),
        patch(
            "vibeops.api.routes_inventory.list_networks",
            return_value=NetworksResult(networks=[net]),
        ),
    ):
        r = c.get("/api/inventory")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["instances"][0]["name"] == "vm-1"
    assert body["instances"][0]["monthly_cost_usd"] == 411.5
    assert body["disks"][0]["name"] == "disk-1"
    assert body["disks"][0]["monthly_cost_usd"] == 17.0
    assert body["images"][0]["name"] == "img-1"
    assert body["images"][0]["monthly_cost_usd"] is None
    assert body["networks"][0]["name"] == "default"


def test_delete_instance_requires_credentials() -> None:
    assert _client().delete("/api/inventory/instance/us-central1-a/vm-1").status_code == 400


def test_delete_disk_requires_credentials() -> None:
    assert _client().delete("/api/inventory/disk/us-central1-a/disk-1").status_code == 400


def test_delete_image_requires_credentials() -> None:
    assert _client().delete("/api/inventory/image/img-1").status_code == 400


def test_delete_network_requires_credentials() -> None:
    assert _client().delete("/api/inventory/network/default").status_code == 400


def test_delete_instance_with_context_calls_tool() -> None:
    c = _client()
    session = get_store().get(c.cookies.get(SESSION_COOKIE))
    assert session is not None
    session.gcp_context = object()
    with patch("vibeops.api.routes_inventory.delete_instance") as mock_delete:
        r = c.delete("/api/inventory/instance/us-central1-a/vm-1")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    mock_delete.assert_called_once()


def test_delete_disk_with_context_calls_tool() -> None:
    c = _client()
    session = get_store().get(c.cookies.get(SESSION_COOKIE))
    assert session is not None
    session.gcp_context = object()
    with patch("vibeops.api.routes_inventory.delete_disk") as mock_delete:
        r = c.delete("/api/inventory/disk/us-central1-a/disk-1")
    assert r.status_code == 200
    mock_delete.assert_called_once()


def test_delete_image_with_context_calls_tool() -> None:
    c = _client()
    session = get_store().get(c.cookies.get(SESSION_COOKIE))
    assert session is not None
    session.gcp_context = object()
    with patch("vibeops.api.routes_inventory.delete_image") as mock_delete:
        r = c.delete("/api/inventory/image/img-1")
    assert r.status_code == 200
    mock_delete.assert_called_once()


def test_delete_network_with_context_calls_tool() -> None:
    c = _client()
    session = get_store().get(c.cookies.get(SESSION_COOKIE))
    assert session is not None
    session.gcp_context = object()
    with patch("vibeops.api.routes_inventory.delete_network") as mock_delete:
        r = c.delete("/api/inventory/network/default")
    assert r.status_code == 200
    mock_delete.assert_called_once()


def test_demo_inventory_returns_simulated_resources() -> None:
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
            monthly_cost_usd=411.5,
        )
    ]
    session.demo_disks = [
        Disk(name="vibeops-demo-gpu-vm-boot", zone="us-central1-a", size_gb=100, type="pd-ssd")
    ]
    session.demo_images = [CustomImage(name="vibeops-demo-base-image", disk_size_gb=50)]
    session.demo_networks = [Network(name="default", self_link="", auto_create_subnetworks=True)]
    r = c.get("/api/inventory")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["instances"][0]["name"] == "vibeops-demo-gpu-vm"
    assert body["disks"][0]["name"] == "vibeops-demo-gpu-vm-boot"
    assert body["images"][0]["name"] == "vibeops-demo-base-image"
    assert body["networks"][0]["name"] == "default"


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
    r = c.delete("/api/inventory/instance/us-central1-a/vibeops-demo-gpu-vm")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert session.demo_vms == []


def test_demo_delete_removes_simulated_disk() -> None:
    c = _client()
    session = get_store().get(c.cookies.get(SESSION_COOKIE))
    assert session is not None
    session.demo_mode = True
    session.demo_disks = [
        Disk(name="disk-1", zone="us-central1-a", size_gb=100, type="pd-ssd")
    ]
    r = c.delete("/api/inventory/disk/us-central1-a/disk-1")
    assert r.status_code == 200
    assert session.demo_disks == []


def test_demo_delete_removes_simulated_image() -> None:
    c = _client()
    session = get_store().get(c.cookies.get(SESSION_COOKIE))
    assert session is not None
    session.demo_mode = True
    session.demo_images = [CustomImage(name="img-1", disk_size_gb=50)]
    r = c.delete("/api/inventory/image/img-1")
    assert r.status_code == 200
    assert session.demo_images == []


def test_demo_delete_removes_simulated_network() -> None:
    c = _client()
    session = get_store().get(c.cookies.get(SESSION_COOKIE))
    assert session is not None
    session.demo_mode = True
    session.demo_networks = [Network(name="default", self_link="", auto_create_subnetworks=True)]
    r = c.delete("/api/inventory/network/default")
    assert r.status_code == 200
    assert session.demo_networks == []
