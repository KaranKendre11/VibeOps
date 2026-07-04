from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vibeops.core.errors import GCPToolError
from vibeops.core.gcp_context import GcpContext
from vibeops.models.results import (
    CustomImagesResult,
    DisksResult,
    MachineTypesResult,
    NetworksResult,
    OsImagesResult,
    QuotaResult,
    ZonesWithAcceleratorResult,
)


def _ctx() -> GcpContext:
    ctx = MagicMock(spec=GcpContext)
    ctx.project_id = "test-project"
    ctx.credentials = MagicMock()
    ctx.get_cached.return_value = None
    ctx.set_cached.return_value = None
    return ctx


class TestListZonesWithAccelerator:
    def test_returns_zones_matching_gpu_type(self) -> None:
        ctx = _ctx()
        mock_item = MagicMock()
        mock_item.name = "nvidia-tesla-t4"
        mock_scoped = MagicMock()
        mock_scoped.accelerator_types = [mock_item]

        with patch("vibeops.tools.compute.compute_v1.AcceleratorTypesClient") as MockClient:
            MockClient.return_value.aggregated_list.return_value = [
                ("zones/us-central1-a", mock_scoped)
            ]
            from vibeops.tools.compute import list_zones_with_accelerator
            result = list_zones_with_accelerator(ctx, "nvidia-tesla-t4")

        assert isinstance(result, ZonesWithAcceleratorResult)
        assert len(result.zones) == 1
        assert result.zones[0].zone == "us-central1-a"
        assert result.zones[0].region == "us-central1"

    def test_filters_non_matching_gpu_types(self) -> None:
        ctx = _ctx()
        mock_item = MagicMock()
        mock_item.name = "nvidia-l4"
        mock_scoped = MagicMock()
        mock_scoped.accelerator_types = [mock_item]

        with patch("vibeops.tools.compute.compute_v1.AcceleratorTypesClient") as MockClient:
            MockClient.return_value.aggregated_list.return_value = [
                ("zones/us-central1-a", mock_scoped)
            ]
            from vibeops.tools.compute import list_zones_with_accelerator
            result = list_zones_with_accelerator(ctx, "nvidia-tesla-t4")

        assert len(result.zones) == 0

    def test_skips_non_zone_keys(self) -> None:
        ctx = _ctx()
        with patch("vibeops.tools.compute.compute_v1.AcceleratorTypesClient") as MockClient:
            MockClient.return_value.aggregated_list.return_value = [
                ("regions/us-central1", MagicMock())
            ]
            from vibeops.tools.compute import list_zones_with_accelerator
            result = list_zones_with_accelerator(ctx, "nvidia-tesla-t4")

        assert len(result.zones) == 0

    def test_raises_gcp_tool_error_on_api_failure(self) -> None:
        ctx = _ctx()
        from google.api_core import exceptions as gcp_exc

        with patch("vibeops.tools.compute.compute_v1.AcceleratorTypesClient") as MockClient:
            MockClient.return_value.aggregated_list.side_effect = gcp_exc.ServiceUnavailable("down")
            from vibeops.tools.compute import list_zones_with_accelerator

            with pytest.raises(GCPToolError):
                list_zones_with_accelerator(ctx, "nvidia-tesla-t4")


class TestListMachineTypes:
    def test_returns_gpu_compatible_machines(self) -> None:
        ctx = _ctx()
        mock_mt = MagicMock()
        mock_mt.name = "n1-standard-8"
        mock_mt.guest_cpus = 8
        mock_mt.memory_mb = 30720
        mock_mt2 = MagicMock()
        mock_mt2.name = "e2-standard-4"
        mock_mt2.guest_cpus = 4
        mock_mt2.memory_mb = 16384

        with patch("vibeops.tools.compute.compute_v1.MachineTypesClient") as MockClient:
            MockClient.return_value.list.return_value = [mock_mt, mock_mt2]
            from vibeops.tools.compute import list_machine_types
            result = list_machine_types(ctx, "us-central1-a", gpu_compatible=True)

        assert isinstance(result, MachineTypesResult)
        names = [m.name for m in result.machine_types]
        assert "n1-standard-8" in names
        assert "e2-standard-4" not in names

    def test_returns_correct_memory_gb(self) -> None:
        ctx = _ctx()
        mock_mt = MagicMock()
        mock_mt.name = "n1-standard-8"
        mock_mt.guest_cpus = 8
        mock_mt.memory_mb = 30720

        with patch("vibeops.tools.compute.compute_v1.MachineTypesClient") as MockClient:
            MockClient.return_value.list.return_value = [mock_mt]
            from vibeops.tools.compute import list_machine_types
            result = list_machine_types(ctx, "us-central1-a", gpu_compatible=True)

        assert result.machine_types[0].memory_gb == pytest.approx(30.0, abs=0.5)


class TestGetAcceleratorQuota:
    def test_returns_correct_quota(self) -> None:
        ctx = _ctx()
        mock_quota = MagicMock()
        mock_quota.metric = "NVIDIA_T4_GPUS"
        mock_quota.limit = 4
        mock_quota.usage = 1
        mock_region = MagicMock()
        mock_region.quotas = [mock_quota]

        with patch("vibeops.tools.compute.compute_v1.RegionsClient") as MockClient:
            MockClient.return_value.get.return_value = mock_region
            from vibeops.tools.compute import get_accelerator_quota
            result = get_accelerator_quota(ctx, "us-central1", "nvidia-tesla-t4")

        assert isinstance(result, QuotaResult)
        assert result.limit == 4
        assert result.usage == 1
        assert result.remaining == 3

    def test_zero_quota_when_metric_not_found(self) -> None:
        ctx = _ctx()
        mock_quota = MagicMock()
        mock_quota.metric = "SOME_OTHER_QUOTA"
        mock_region = MagicMock()
        mock_region.quotas = [mock_quota]

        with patch("vibeops.tools.compute.compute_v1.RegionsClient") as MockClient:
            MockClient.return_value.get.return_value = mock_region
            from vibeops.tools.compute import get_accelerator_quota
            result = get_accelerator_quota(ctx, "us-central1", "nvidia-tesla-t4")

        assert result.limit == 0
        assert result.usage == 0


class TestListOsImages:
    def test_returns_images_from_public_projects(self) -> None:
        ctx = _ctx()
        mock_img = MagicMock()
        mock_img.family = "deeplearning-platform-release"
        mock_img.description = "DL VM image"

        with patch("vibeops.tools.compute.compute_v1.ImagesClient") as MockClient:
            MockClient.return_value.list.return_value = [mock_img]
            from vibeops.tools.compute import list_os_images
            result = list_os_images(ctx)

        assert isinstance(result, OsImagesResult)
        families = [i.family for i in result.images]
        assert "deeplearning-platform-release" in families


class TestListDisks:
    def test_returns_disks_with_short_type_users_and_cost(self) -> None:
        ctx = _ctx()
        mock_disk = MagicMock()
        mock_disk.name = "disk-1"
        mock_disk.size_gb = 100
        mock_disk.type_ = "https://compute/zones/us-central1-a/diskTypes/pd-ssd"
        mock_disk.status = "READY"
        mock_disk.users = ["https://compute/zones/us-central1-a/instances/vm-1"]
        mock_disk.creation_timestamp = "2026-01-01T00:00:00Z"
        mock_scoped = MagicMock()
        mock_scoped.disks = [mock_disk]

        with patch("vibeops.tools.compute.compute_v1.DisksClient") as MockClient:
            MockClient.return_value.aggregated_list.return_value = [
                ("zones/us-central1-a", mock_scoped)
            ]
            from vibeops.tools.compute import list_disks
            result = list_disks(ctx)

        assert isinstance(result, DisksResult)
        assert len(result.disks) == 1
        d = result.disks[0]
        assert d.name == "disk-1"
        assert d.zone == "us-central1-a"
        assert d.type == "pd-ssd"  # shortened from the full URL
        assert d.users == ["vm-1"]  # short instance name
        assert d.monthly_cost_usd == pytest.approx(17.0)  # 100 GB * 0.17

    def test_skips_non_zone_keys(self) -> None:
        ctx = _ctx()
        with patch("vibeops.tools.compute.compute_v1.DisksClient") as MockClient:
            MockClient.return_value.aggregated_list.return_value = [
                ("regions/us-central1", MagicMock())
            ]
            from vibeops.tools.compute import list_disks
            result = list_disks(ctx)

        assert len(result.disks) == 0

    def test_raises_gcp_tool_error_on_failure(self) -> None:
        ctx = _ctx()
        from google.api_core import exceptions as gcp_exc

        with patch("vibeops.tools.compute.compute_v1.DisksClient") as MockClient:
            MockClient.return_value.aggregated_list.side_effect = gcp_exc.ServiceUnavailable("down")
            from vibeops.tools.compute import list_disks

            with pytest.raises(GCPToolError, match="list_disks failed"):
                list_disks(ctx)


class TestListCustomImages:
    def test_returns_project_own_images(self) -> None:
        ctx = _ctx()
        mock_img = MagicMock()
        mock_img.name = "my-image"
        mock_img.disk_size_gb = 50
        mock_img.family = "vibeops"
        mock_img.status = "READY"
        mock_img.creation_timestamp = "2026-01-01T00:00:00Z"

        with patch("vibeops.tools.compute.compute_v1.ImagesClient") as MockClient:
            MockClient.return_value.list.return_value = [mock_img]
            from vibeops.tools.compute import list_custom_images
            result = list_custom_images(ctx)

        assert isinstance(result, CustomImagesResult)
        assert result.images[0].name == "my-image"
        assert result.images[0].disk_size_gb == 50
        assert result.images[0].monthly_cost_usd is None  # usage-based → "—"
        # Only the project's OWN images (not the public OS-image projects).
        MockClient.return_value.list.assert_called_once_with(project="test-project")

    def test_raises_gcp_tool_error_on_failure(self) -> None:
        ctx = _ctx()
        from google.api_core import exceptions as gcp_exc

        with patch("vibeops.tools.compute.compute_v1.ImagesClient") as MockClient:
            MockClient.return_value.list.side_effect = gcp_exc.PermissionDenied("denied")
            from vibeops.tools.compute import list_custom_images

            with pytest.raises(GCPToolError, match="list_custom_images failed"):
                list_custom_images(ctx)


class TestListNetworks:
    def test_returns_networks_fresh_without_cache(self) -> None:
        ctx = _ctx()
        mock_net = MagicMock()
        mock_net.name = "default"
        mock_net.self_link = "https://compute/global/networks/default"
        mock_net.auto_create_subnetworks = True

        with patch("vibeops.tools.compute.compute_v1.NetworksClient") as MockClient:
            MockClient.return_value.list.return_value = [mock_net]
            from vibeops.tools.compute import list_networks
            result = list_networks(ctx)

        assert isinstance(result, NetworksResult)
        assert result.networks[0].name == "default"
        assert result.networks[0].auto_create_subnetworks is True
        MockClient.return_value.list.assert_called_once_with(project="test-project")
        ctx.set_cached.assert_not_called()  # dashboard wants a live view every open

    def test_raises_gcp_tool_error_on_failure(self) -> None:
        ctx = _ctx()
        from google.api_core import exceptions as gcp_exc

        with patch("vibeops.tools.compute.compute_v1.NetworksClient") as MockClient:
            MockClient.return_value.list.side_effect = gcp_exc.ServiceUnavailable("down")
            from vibeops.tools.compute import list_networks

            with pytest.raises(GCPToolError, match="list_networks failed"):
                list_networks(ctx)
