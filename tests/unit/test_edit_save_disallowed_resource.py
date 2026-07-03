from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from vibeops.models.iac import AllowlistResult, TerraformValidationResult, Violation
from vibeops.models.state import FlowStage, GraphState
from vibeops.services.review import apply_user_edit

_ORIGINAL = 'resource "google_compute_instance" "gpu_vm" { name = "ok" }\n'

_WITH_IAM = """\
resource "google_compute_instance" "gpu_vm" { name = "ok" }
resource "google_project_iam_binding" "bad" {
  project = "my-proj"
  role    = "roles/editor"
  members = ["user:foo@example.com"]
}
"""


def _state(tmp_path: Path) -> GraphState:
    (tmp_path / "main.tf").write_text(_ORIGINAL, encoding="utf-8")
    return GraphState(
        user_prompt="test",
        stage=FlowStage.AWAITING_APPROVAL,
        terraform_dir=str(tmp_path),
        terraform_files={"main.tf": _ORIGINAL},
        terraform_files_original={"main.tf": _ORIGINAL},
    )


class TestEditSaveDisallowedResource:
    """Security boundary: allowlist blocks disallowed resource types even if HCL is valid."""

    def test_iam_binding_rejected(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        violation = Violation(resource_type="google_project_iam_binding", line_number=0)

        with patch(
            "vibeops.services.review.validate",
            return_value=TerraformValidationResult(ok=True),
        ), patch(
            "vibeops.services.review.check_resource_allowlist",
            return_value=AllowlistResult(ok=False, violations=[violation]),
        ):
            new_state, err = apply_user_edit(state, "main.tf", _WITH_IAM)

        assert err is not None
        assert "google_project_iam_binding" in err
        assert "not in allowlist" in err

    def test_state_not_updated_on_disallowed(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        violation = Violation(resource_type="google_project_iam_binding", line_number=0)

        with patch(
            "vibeops.services.review.validate",
            return_value=TerraformValidationResult(ok=True),
        ), patch(
            "vibeops.services.review.check_resource_allowlist",
            return_value=AllowlistResult(ok=False, violations=[violation]),
        ):
            new_state, _ = apply_user_edit(state, "main.tf", _WITH_IAM)

        assert new_state.terraform_files["main.tf"] == _ORIGINAL

    def test_file_restored_on_disk_on_disallowed(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        violation = Violation(resource_type="google_project_iam_binding", line_number=0)

        with patch(
            "vibeops.services.review.validate",
            return_value=TerraformValidationResult(ok=True),
        ), patch(
            "vibeops.services.review.check_resource_allowlist",
            return_value=AllowlistResult(ok=False, violations=[violation]),
        ):
            apply_user_edit(state, "main.tf", _WITH_IAM)

        assert (tmp_path / "main.tf").read_text(encoding="utf-8") == _ORIGINAL

    def test_error_message_contains_allowed_list(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        violation = Violation(resource_type="google_storage_bucket", line_number=0)

        with patch(
            "vibeops.services.review.validate",
            return_value=TerraformValidationResult(ok=True),
        ), patch(
            "vibeops.services.review.check_resource_allowlist",
            return_value=AllowlistResult(ok=False, violations=[violation]),
        ):
            _, err = apply_user_edit(state, "main.tf", _WITH_IAM)

        assert err is not None
        assert "google_compute_instance" in err  # allowed type is listed

    def test_allowlist_not_checked_for_variables_tf(self, tmp_path: Path) -> None:
        """Allowlist only applies to main.tf, not variables.tf or outputs.tf."""
        (tmp_path / "variables.tf").write_text("", encoding="utf-8")
        state = _state(tmp_path)
        state = state.model_copy(
            update={"terraform_files": {**state.terraform_files, "variables.tf": ""}}
        )
        valid_vars = 'variable "project_id" { type = string }\n'

        with patch(
            "vibeops.services.review.validate",
            return_value=TerraformValidationResult(ok=True),
        ), patch(
            "vibeops.services.review.check_resource_allowlist"
        ) as mock_al:
            new_state, err = apply_user_edit(state, "variables.tf", valid_vars)

        mock_al.assert_not_called()
        assert err is None
