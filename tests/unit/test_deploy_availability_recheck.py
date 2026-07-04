"""Deploy-time defence: machine-type + GPU availability and quota are re-checked before apply.

Capacity and quota can change between architecture selection and the moment the user approves
and deploys. ``deployment_agent`` re-validates the chosen machine type / accelerator / quota in
the selected zone immediately before ``terraform plan``/``apply`` and, on a definitive
"unavailable" verdict, fails fast with an actionable message and excludes the zone (so a
re-discovery skips it) instead of surfacing a raw terraform error. An inconclusive check (the
availability API itself erroring) must NOT block a valid deploy.

Everything is mocked — no real GCP is touched.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from vibeops.agents.deployment import deployment_agent
from vibeops.core.errors import GCPToolError
from vibeops.core.gcp_context import GcpContext
from vibeops.models.deployment import (
    ApplyResult,
    DeploymentOutcome,
    DeploymentPhase,
    PlanResult,
    StateResource,
)
from vibeops.models.results import (
    MachineType,
    MachineTypesResult,
    QuotaResult,
    ZoneAvailability,
    ZonesWithAcceleratorResult,
)
from vibeops.models.spec import (
    ComputeSpec,
    DeploymentSpec,
    GpuType,
    NetworkSpec,
    StorageSpec,
)
from vibeops.models.state import FlowStage, GraphState
from vibeops.terraform.errors import TerraformApplyError

_ALLOWED = 'resource "google_compute_instance" "gpu_vm" { name = "ok" }\n'
_ZONE = "us-central1-a"
_REGION = "us-central1"
_GPU = "nvidia-tesla-t4"  # == GpuType.T4.value
_MACHINE = "n1-standard-8"


def _ctx() -> GcpContext:
    return GcpContext(service_account_info={"type": "service_account"}, project_id="test-project")


def _config(ctx: GcpContext) -> dict[str, object]:
    return {"configurable": {"gcp_context": ctx}}


def _spec(machine_type: str = _MACHINE, zone: str = _ZONE, gpu_count: int = 1) -> DeploymentSpec:
    return DeploymentSpec(
        compute=ComputeSpec(
            machine_type=machine_type,
            zone=zone,
            gpu_type=GpuType.T4,
            gpu_count=gpu_count,
            preemptible=False,
        ),
        storage=StorageSpec(
            disk_size_gb=100,
            os_image_family="common-cu121",
            os_image_project="deeplearning-platform-release",
        ),
        network=NetworkSpec(network_name="default"),
        project_id="test-project",
    )


def _state(tmp_path: Path, *, spec: DeploymentSpec | None = None, excluded: list[str] | None = None) -> GraphState:
    (tmp_path / "main.tf").write_text(_ALLOWED, encoding="utf-8")  # clears the allowlist gate
    return GraphState(
        user_prompt="deploy",
        terraform_dir=str(tmp_path),
        approved=True,
        stage=FlowStage.AWAITING_APPROVAL,
        deployment_spec=spec if spec is not None else _spec(),
        excluded_zones=list(excluded or []),
    )


def _machines(*names: str) -> MachineTypesResult:
    return MachineTypesResult(
        zone=_ZONE,
        machine_types=[
            MachineType(name=n, cpus=8, memory_gb=32.0, gpu_compatible=True) for n in names
        ],
    )


def _zones() -> ZonesWithAcceleratorResult:
    return ZonesWithAcceleratorResult(
        gpu_type=_GPU,
        zones=[
            ZoneAvailability(
                zone=_ZONE, region=_REGION, gpu_available=True, quota_total=4, quota_used=0
            )
        ],
    )


def _quota(limit: int = 4, usage: int = 0) -> QuotaResult:
    return QuotaResult(region=_REGION, gpu_type=_GPU, limit=limit, usage=usage)


class TestDeployAvailabilityRecheck:
    def test_available_machine_proceeds_and_deploys(self, tmp_path: Path) -> None:
        """A machine/GPU still available and within quota clears the gate and deploys as before."""
        resources = [StateResource(type="google_compute_instance", name="vm", zone=_ZONE)]
        with (
            patch("vibeops.tools.compute.list_machine_types", return_value=_machines(_MACHINE)),
            patch("vibeops.tools.compute.list_zones_with_accelerator", return_value=_zones()),
            patch("vibeops.tools.compute.get_accelerator_quota", return_value=_quota()),
            patch("vibeops.agents.deployment.runner.write_sa_credentials"),
            patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="p")) as plan_mock,
            patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="done", resources_created=1)),
            patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=resources),
        ):
            result = deployment_agent(_state(tmp_path), _config(_ctx()))

        plan_mock.assert_called_once()  # got past the availability gate
        assert result.deployment_phase == DeploymentPhase.SUCCEEDED
        assert result.deployment_outcome == DeploymentOutcome.SUCCEEDED
        assert result.excluded_zones == []

    def test_machine_no_longer_offered_blocks_and_excludes_zone(self, tmp_path: Path) -> None:
        """Selected machine type absent from the zone → fail fast, exclude zone, no terraform."""
        with (
            patch("vibeops.tools.compute.list_machine_types", return_value=_machines("g2-standard-4")),
            patch("vibeops.tools.compute.list_zones_with_accelerator", return_value=_zones()),
            patch("vibeops.tools.compute.get_accelerator_quota", return_value=_quota()),
            patch("vibeops.agents.deployment.runner.plan") as plan_mock,
            patch("vibeops.agents.deployment.runner.apply") as apply_mock,
        ):
            result = deployment_agent(_state(tmp_path), _config(_ctx()))

        plan_mock.assert_not_called()
        apply_mock.assert_not_called()
        assert result.deployment_phase == DeploymentPhase.FAILED
        assert result.deployment_outcome == DeploymentOutcome.PLAN_FAILED
        error = result.deployment_error or ""
        assert _MACHINE in error
        assert _ZONE in error
        assert "excluded" in error.lower()
        assert _ZONE in result.excluded_zones
        assert result.retry_requested is False

    def test_gpu_not_available_in_zone_blocks(self, tmp_path: Path) -> None:
        """Accelerator no longer offered in the zone → blocked with a GPU-specific reason."""
        empty_zones = ZonesWithAcceleratorResult(gpu_type=_GPU, zones=[])
        with (
            patch("vibeops.tools.compute.list_machine_types", return_value=_machines(_MACHINE)),
            patch("vibeops.tools.compute.list_zones_with_accelerator", return_value=empty_zones),
            patch("vibeops.tools.compute.get_accelerator_quota", return_value=_quota()),
            patch("vibeops.agents.deployment.runner.plan") as plan_mock,
        ):
            result = deployment_agent(_state(tmp_path), _config(_ctx()))

        plan_mock.assert_not_called()
        assert result.deployment_outcome == DeploymentOutcome.PLAN_FAILED
        assert _GPU in (result.deployment_error or "")
        assert _ZONE in result.excluded_zones

    def test_exhausted_quota_blocks_and_names_quota(self, tmp_path: Path) -> None:
        """No remaining GPU quota in the region → blocked with a quota-specific reason."""
        with (
            patch("vibeops.tools.compute.list_machine_types", return_value=_machines(_MACHINE)),
            patch("vibeops.tools.compute.list_zones_with_accelerator", return_value=_zones()),
            patch("vibeops.tools.compute.get_accelerator_quota", return_value=_quota(limit=2, usage=2)),
            patch("vibeops.agents.deployment.runner.plan") as plan_mock,
        ):
            result = deployment_agent(_state(tmp_path), _config(_ctx()))

        plan_mock.assert_not_called()
        assert result.deployment_outcome == DeploymentOutcome.PLAN_FAILED
        assert "quota" in (result.deployment_error or "").lower()
        assert _ZONE in result.excluded_zones

    def test_excluded_zone_not_duplicated(self, tmp_path: Path) -> None:
        """Re-blocking an already-excluded zone keeps a single entry."""
        with (
            patch("vibeops.tools.compute.list_machine_types", return_value=_machines()),
            patch("vibeops.tools.compute.list_zones_with_accelerator", return_value=_zones()),
            patch("vibeops.tools.compute.get_accelerator_quota", return_value=_quota()),
            patch("vibeops.agents.deployment.runner.plan"),
        ):
            result = deployment_agent(_state(tmp_path, excluded=[_ZONE]), _config(_ctx()))

        assert result.excluded_zones.count(_ZONE) == 1

    def test_inconclusive_check_fails_open_and_deploys(self, tmp_path: Path) -> None:
        """If the availability API itself errors, do NOT block — terraform stays the backstop."""
        resources = [StateResource(type="google_compute_instance", name="vm", zone=_ZONE)]
        with (
            patch(
                "vibeops.tools.compute.list_machine_types",
                side_effect=GCPToolError("compute API unreachable"),
            ),
            patch("vibeops.agents.deployment.runner.write_sa_credentials"),
            patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="p")) as plan_mock,
            patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="done", resources_created=1)),
            patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=resources),
        ):
            result = deployment_agent(_state(tmp_path), _config(_ctx()))

        plan_mock.assert_called_once()
        assert result.deployment_outcome == DeploymentOutcome.SUCCEEDED
        assert result.excluded_zones == []

    def test_no_gcp_context_skips_recheck(self, tmp_path: Path) -> None:
        """Without a GcpContext the re-check is skipped (cannot verify) and deploy proceeds."""
        resources = [StateResource(type="google_compute_instance", name="vm", zone=_ZONE)]
        with (
            patch("vibeops.tools.compute.list_machine_types") as mt_mock,
            patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="p")) as plan_mock,
            patch("vibeops.agents.deployment.runner.apply", return_value=ApplyResult(full_log="done", resources_created=1)),
            patch("vibeops.agents.deployment.runner.parse_state_resources", return_value=resources),
        ):
            result = deployment_agent(_state(tmp_path))  # no config → no gcp_context

        mt_mock.assert_not_called()
        plan_mock.assert_called_once()
        assert result.deployment_outcome == DeploymentOutcome.SUCCEEDED


class TestZoneLevelApplyFailureExclusion:
    """A zone-level terraform apply failure (capacity/availability) excludes the zone too."""

    def test_capacity_apply_failure_excludes_zone(self, tmp_path: Path) -> None:
        err = TerraformApplyError(
            "Error: googleapi: Error 503: The zone 'us-central1-a' does not have enough "
            "resources available to fulfill the request. Try a different zone.",
            partial_state=False,
            created_resources=[],
        )
        with (
            patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="p")),
            patch("vibeops.agents.deployment.runner.apply", side_effect=err),
        ):
            result = deployment_agent(_state(tmp_path))  # no ctx → pre-check skipped, apply runs

        assert result.deployment_phase == DeploymentPhase.FAILED
        assert result.deployment_outcome == DeploymentOutcome.FULL_FAIL
        assert _ZONE in result.excluded_zones

    def test_generic_apply_failure_does_not_exclude_zone(self, tmp_path: Path) -> None:
        err = TerraformApplyError(
            "Error: failed to attach disk: internal error",
            partial_state=False,
            created_resources=[],
        )
        with (
            patch("vibeops.agents.deployment.runner.plan", return_value=PlanResult(plan_file="p")),
            patch("vibeops.agents.deployment.runner.apply", side_effect=err),
        ):
            result = deployment_agent(_state(tmp_path))

        assert result.deployment_outcome == DeploymentOutcome.FULL_FAIL
        assert result.excluded_zones == []
