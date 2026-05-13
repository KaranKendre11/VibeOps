from __future__ import annotations

from unittest.mock import MagicMock, patch

from vibeops.core.gcp_context import GcpContext
from vibeops.tools.compute import list_zones_with_accelerator


def _real_ctx() -> GcpContext:
    ctx = GcpContext(service_account_info={"type": "service_account"}, project_id="p")
    ctx._creds = MagicMock()  # bypass real credential construction
    return ctx


def test_same_args_calls_sdk_once() -> None:
    ctx = _real_ctx()
    mock_item = MagicMock()
    mock_item.name = "nvidia-tesla-t4"
    mock_scoped = MagicMock()
    mock_scoped.accelerator_types = [mock_item]

    with patch("vibeops.tools.compute.compute_v1.AcceleratorTypesClient") as MockClient:
        MockClient.return_value.aggregated_list.return_value = [
            ("zones/us-central1-a", mock_scoped)
        ]
        r1 = list_zones_with_accelerator(ctx, "nvidia-tesla-t4")
        r2 = list_zones_with_accelerator(ctx, "nvidia-tesla-t4")

    assert MockClient.return_value.aggregated_list.call_count == 1
    assert r1 == r2


def test_different_args_calls_sdk_twice() -> None:
    ctx = _real_ctx()

    with patch("vibeops.tools.compute.compute_v1.AcceleratorTypesClient") as MockClient:
        MockClient.return_value.aggregated_list.return_value = []
        list_zones_with_accelerator(ctx, "nvidia-tesla-t4")
        list_zones_with_accelerator(ctx, "nvidia-l4")

    assert MockClient.return_value.aggregated_list.call_count == 2


def test_clear_cache_forces_refetch() -> None:
    ctx = _real_ctx()

    with patch("vibeops.tools.compute.compute_v1.AcceleratorTypesClient") as MockClient:
        MockClient.return_value.aggregated_list.return_value = []
        list_zones_with_accelerator(ctx, "nvidia-tesla-t4")
        ctx.clear_cache()
        list_zones_with_accelerator(ctx, "nvidia-tesla-t4")

    assert MockClient.return_value.aggregated_list.call_count == 2
