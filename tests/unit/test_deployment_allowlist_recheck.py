"""Deploy-time defence: the resource allowlist is re-checked immediately before terraform apply.

The review-screen check can be bypassed if the on-disk *.tf files are tampered with after review,
so ``deployment_agent`` fails closed when a disallowed (or unparseable) resource is present.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from vibeops.agents.deployment import deployment_agent
from vibeops.models.deployment import DeploymentOutcome, DeploymentPhase
from vibeops.models.state import FlowStage, GraphState
from vibeops.terraform.errors import TerraformPlanError

_ALLOWED = 'resource "google_compute_instance" "gpu_vm" { name = "ok" }\n'
_TAMPERED = _ALLOWED + 'resource "google_storage_bucket" "leak" { name = "exfil" }\n'
_SNEAKY_IAM = 'resource "google_project_iam_binding" "bad" { role = "roles/editor" }\n'


def _state(tmp_path: Path) -> GraphState:
    return GraphState(
        user_prompt="deploy",
        terraform_dir=str(tmp_path),
        approved=True,
        stage=FlowStage.AWAITING_APPROVAL,
    )


class TestDeploymentAllowlistRecheck:
    def test_tampered_main_tf_blocks_deploy(self, tmp_path: Path) -> None:
        (tmp_path / "main.tf").write_text(_TAMPERED, encoding="utf-8")
        with (
            patch("vibeops.agents.deployment.runner.plan") as plan_mock,
            patch("vibeops.agents.deployment.runner.apply") as apply_mock,
        ):
            result = deployment_agent(_state(tmp_path))

        plan_mock.assert_not_called()
        apply_mock.assert_not_called()
        assert result.deployment_phase == DeploymentPhase.FAILED
        assert result.deployment_outcome == DeploymentOutcome.PLAN_FAILED
        assert result.deployment_error is not None
        assert "google_storage_bucket" in result.deployment_error

    def test_disallowed_resource_in_secondary_file_blocks_deploy(self, tmp_path: Path) -> None:
        """main.tf is clean but a disallowed resource hides in outputs.tf — still blocked."""
        (tmp_path / "main.tf").write_text(_ALLOWED, encoding="utf-8")
        (tmp_path / "outputs.tf").write_text(_SNEAKY_IAM, encoding="utf-8")
        with (
            patch("vibeops.agents.deployment.runner.plan") as plan_mock,
            patch("vibeops.agents.deployment.runner.apply") as apply_mock,
        ):
            result = deployment_agent(_state(tmp_path))

        plan_mock.assert_not_called()
        apply_mock.assert_not_called()
        assert result.deployment_outcome == DeploymentOutcome.PLAN_FAILED
        assert "google_project_iam_binding" in (result.deployment_error or "")

    def test_unparseable_tf_blocks_deploy(self, tmp_path: Path) -> None:
        """Fail closed even if a *.tf file can't be parsed by the allowlist checker."""
        # Unclosed block — hcl2 raises, so the guard can't confirm the config is safe.
        (tmp_path / "main.tf").write_text(
            'resource "google_compute_instance" "vm" {\n', encoding="utf-8"
        )
        with (
            patch("vibeops.agents.deployment.runner.plan") as plan_mock,
            patch("vibeops.agents.deployment.runner.apply") as apply_mock,
        ):
            result = deployment_agent(_state(tmp_path))

        plan_mock.assert_not_called()
        apply_mock.assert_not_called()
        assert result.deployment_outcome == DeploymentOutcome.PLAN_FAILED
        assert "could not verify resource allowlist" in (result.deployment_error or "")

    def test_clean_dir_proceeds_past_allowlist_to_plan(self, tmp_path: Path) -> None:
        """An allowed-only work dir clears the guard and reaches terraform plan."""
        (tmp_path / "main.tf").write_text(_ALLOWED, encoding="utf-8")
        with patch(
            "vibeops.agents.deployment.runner.plan",
            side_effect=TerraformPlanError("boom"),
        ) as plan_mock:
            result = deployment_agent(_state(tmp_path))

        plan_mock.assert_called_once()  # got past the allowlist guard
        assert result.deployment_outcome == DeploymentOutcome.PLAN_FAILED
