from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vibeops.core.errors import GCPToolError
from vibeops.core.gcp_context import GcpContext
from vibeops.models.results import (
    MachineTypesResult,
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
