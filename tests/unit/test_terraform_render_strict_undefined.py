from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from jinja2 import UndefinedError

from vibeops.models.spec import ComputeSpec, DeploymentSpec, GpuType, NetworkSpec, StorageSpec
from vibeops.terraform.render import _build_context, render_templates


def _spec() -> DeploymentSpec:
    return DeploymentSpec(
        compute=ComputeSpec(
            machine_type="n1-standard-8",
            zone="us-central1-a",
            gpu_type=GpuType.T4,
            gpu_count=1,
            preemptible=False,
        ),
        storage=StorageSpec(
            disk_size_gb=100,
            os_image_family="common-cu121",
            os_image_project="deeplearning-platform-release",
        ),
        network=NetworkSpec(network_name="default"),
        project_id="my-test-project",
    )


def test_missing_context_key_raises_undefined_error(tmp_path: Path) -> None:
    """StrictUndefined must cause render to raise when a key is absent."""
    spec = _spec()
    ctx = _build_context(spec, "")
    # Remove a key that the template needs
    ctx.pop("zone")

    with patch("vibeops.terraform.render._build_context", return_value=ctx):
        with pytest.raises(UndefinedError):
            render_templates(spec, tmp_path)


def test_missing_machine_type_raises(tmp_path: Path) -> None:
    spec = _spec()
    ctx = _build_context(spec, "")
    ctx.pop("machine_type")

    with patch("vibeops.terraform.render._build_context", return_value=ctx):
        with pytest.raises(UndefinedError):
            render_templates(spec, tmp_path)
