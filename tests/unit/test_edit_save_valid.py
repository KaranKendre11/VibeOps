from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from vibeops.models.iac import TerraformValidationResult
from vibeops.models.state import FlowStage, GraphState
from vibeops.ui.review import apply_user_edit

_VALID_HCL = """\
resource "google_compute_instance" "gpu_vm" {
  name         = "test"
  machine_type = "n1-standard-4"
  zone         = "us-central1-a"

  boot_disk {
    initialize_params { image = "debian-cloud/debian-11" }
  }

  network_interface { network = "default" }
}
"""


def _state(tmp_path: Path) -> GraphState:
    main = tmp_path / "main.tf"
    main.write_text(_VALID_HCL, encoding="utf-8")
    return GraphState(
        user_prompt="test",
        stage=FlowStage.AWAITING_APPROVAL,
        terraform_dir=str(tmp_path),
        terraform_files={"main.tf": _VALID_HCL, "variables.tf": "", "outputs.tf": ""},
        terraform_files_original={"main.tf": _VALID_HCL, "variables.tf": "", "outputs.tf": ""},
    )


class TestEditSaveValid:
    def test_state_updated_on_success(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        edited = _VALID_HCL.replace("test", "edited-vm")

        with patch(
            "vibeops.ui.review.validate",
            return_value=TerraformValidationResult(ok=True),
        ), patch(
            "vibeops.ui.review.check_resource_allowlist",
            return_value=MagicMock(ok=True, violations=[]),
        ):
            new_state, err = apply_user_edit(state, "main.tf", edited)

        assert err is None
        assert new_state.terraform_files["main.tf"] == edited

    def test_cost_estimate_stale_set(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        edited = _VALID_HCL.replace("test", "another-vm")

        with patch(
            "vibeops.ui.review.validate",
            return_value=TerraformValidationResult(ok=True),
        ), patch(
            "vibeops.ui.review.check_resource_allowlist",
            return_value=MagicMock(ok=True, violations=[]),
        ):
            new_state, err = apply_user_edit(state, "main.tf", edited)

        assert err is None
        assert new_state.cost_estimate_stale is True

    def test_original_state_unchanged_on_success(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        original_files = dict(state.terraform_files)
        edited = _VALID_HCL.replace("test", "yet-another")

        with patch(
            "vibeops.ui.review.validate",
            return_value=TerraformValidationResult(ok=True),
        ), patch(
            "vibeops.ui.review.check_resource_allowlist",
            return_value=MagicMock(ok=True, violations=[]),
        ):
            new_state, _ = apply_user_edit(state, "main.tf", edited)

        assert state.terraform_files == original_files
        assert new_state is not state

    def test_file_written_to_disk(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        edited = _VALID_HCL.replace("test", "disk-test-vm")

        with patch(
            "vibeops.ui.review.validate",
            return_value=TerraformValidationResult(ok=True),
        ), patch(
            "vibeops.ui.review.check_resource_allowlist",
            return_value=MagicMock(ok=True, violations=[]),
        ):
            apply_user_edit(state, "main.tf", edited)

        assert (tmp_path / "main.tf").read_text(encoding="utf-8") == edited
