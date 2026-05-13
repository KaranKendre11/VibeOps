from __future__ import annotations

import json
import os

import pytest

from vibeops.core.gcp_context import GcpContext
from vibeops.tools.compute import (
    get_accelerator_quota,
    list_machine_types,
    list_os_images,
    list_zones_with_accelerator,
)
from vibeops.tools.resource_manager import list_existing_networks

pytestmark = pytest.mark.live


def _ctx() -> GcpContext:
    sa_path = os.environ.get("VIBEOPS_SA_JSON_PATH")
    project_id = os.environ.get("VIBEOPS_PROJECT_ID")
    if not sa_path or not project_id:
        pytest.skip("Set VIBEOPS_SA_JSON_PATH and VIBEOPS_PROJECT_ID to run live tests")
    with open(sa_path) as f:
        sa_info: dict[str, object] = json.load(f)
    return GcpContext(service_account_info=sa_info, project_id=project_id)


def test_list_zones_with_t4() -> None:
    ctx = _ctx()
    result = list_zones_with_accelerator(ctx, "nvidia-tesla-t4")
    assert result.gpu_type == "nvidia-tesla-t4"
    assert len(result.zones) > 0


def test_list_machine_types_in_zone() -> None:
    ctx = _ctx()
    zones_result = list_zones_with_accelerator(ctx, "nvidia-tesla-t4")
    assert zones_result.zones
    zone = zones_result.zones[0].zone
    result = list_machine_types(ctx, zone, gpu_compatible=True)
    assert len(result.machine_types) > 0


def test_get_accelerator_quota() -> None:
    ctx = _ctx()
    zones_result = list_zones_with_accelerator(ctx, "nvidia-tesla-t4")
    assert zones_result.zones
    region = zones_result.zones[0].region
    result = get_accelerator_quota(ctx, region, "nvidia-tesla-t4")
    assert result.region == region
    assert result.limit >= 0


def test_list_os_images() -> None:
    ctx = _ctx()
    result = list_os_images(ctx, family_filter=None)
    assert len(result.images) > 0


def test_list_existing_networks() -> None:
    ctx = _ctx()
    result = list_existing_networks(ctx)
    assert len(result.networks) >= 1
    names = [n.name for n in result.networks]
    assert "default" in names
