from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

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

# A disallowed resource smuggled into a NON-main.tf file — the bypass this hardening closes.
_SNEAKY_BUCKET = 'resource "google_storage_bucket" "leak" { name = "exfil" }\n'


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

        with (
            patch(
                "vibeops.services.review.validate",
                return_value=TerraformValidationResult(ok=True),
            ),
            patch(
                "vibeops.services.review.check_dir_allowlist",
                return_value=AllowlistResult(ok=False, violations=[violation]),
            ),
        ):
            new_state, err = apply_user_edit(state, "main.tf", _WITH_IAM)

        assert err is not None
        assert "google_project_iam_binding" in err
        assert "not in allowlist" in err

    def test_state_not_updated_on_disallowed(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        violation = Violation(resource_type="google_project_iam_binding", line_number=0)

        with (
            patch(
                "vibeops.services.review.validate",
                return_value=TerraformValidationResult(ok=True),
            ),
            patch(
                "vibeops.services.review.check_dir_allowlist",
                return_value=AllowlistResult(ok=False, violations=[violation]),
            ),
        ):
            new_state, _ = apply_user_edit(state, "main.tf", _WITH_IAM)

        assert new_state.terraform_files["main.tf"] == _ORIGINAL

    def test_file_restored_on_disk_on_disallowed(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        violation = Violation(resource_type="google_project_iam_binding", line_number=0)

        with (
            patch(
                "vibeops.services.review.validate",
                return_value=TerraformValidationResult(ok=True),
            ),
            patch(
                "vibeops.services.review.check_dir_allowlist",
                return_value=AllowlistResult(ok=False, violations=[violation]),
            ),
        ):
            apply_user_edit(state, "main.tf", _WITH_IAM)

        assert (tmp_path / "main.tf").read_text(encoding="utf-8") == _ORIGINAL

    def test_error_message_contains_allowed_list(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        violation = Violation(resource_type="google_storage_bucket", line_number=0)

        with (
            patch(
                "vibeops.services.review.validate",
                return_value=TerraformValidationResult(ok=True),
            ),
            patch(
                "vibeops.services.review.check_dir_allowlist",
                return_value=AllowlistResult(ok=False, violations=[violation]),
            ),
        ):
            _, err = apply_user_edit(state, "main.tf", _WITH_IAM)

        assert err is not None
        assert "google_compute_instance" in err  # allowed type is listed


class TestEditAllowlistCoversEveryFile:
    """Regression for the allowlist bypass: EVERY *.tf is checked, not just main.tf.

    These exercise the real ``check_dir_allowlist`` (only ``validate`` is stubbed, since the
    terraform binary isn't available in unit tests).
    """

    def _multi_file_state(self, tmp_path: Path) -> GraphState:
        (tmp_path / "main.tf").write_text(_ORIGINAL, encoding="utf-8")
        (tmp_path / "outputs.tf").write_text("", encoding="utf-8")
        return GraphState(
            user_prompt="test",
            stage=FlowStage.AWAITING_APPROVAL,
            terraform_dir=str(tmp_path),
            terraform_files={"main.tf": _ORIGINAL, "outputs.tf": ""},
            terraform_files_original={"main.tf": _ORIGINAL, "outputs.tf": ""},
        )

    def test_disallowed_resource_in_outputs_tf_rejected(self, tmp_path: Path) -> None:
        """A disallowed resource added via outputs.tf must be rejected — the old bypass."""
        state = self._multi_file_state(tmp_path)
        with patch(
            "vibeops.services.review.validate",
            return_value=TerraformValidationResult(ok=True),
        ):
            _, err = apply_user_edit(state, "outputs.tf", _SNEAKY_BUCKET)

        assert err is not None
        assert "google_storage_bucket" in err
        assert "not in allowlist" in err

    def test_outputs_tf_restored_on_disk_when_disallowed(self, tmp_path: Path) -> None:
        state = self._multi_file_state(tmp_path)
        with patch(
            "vibeops.services.review.validate",
            return_value=TerraformValidationResult(ok=True),
        ):
            apply_user_edit(state, "outputs.tf", _SNEAKY_BUCKET)

        assert (tmp_path / "outputs.tf").read_text(encoding="utf-8") == ""

    def test_state_not_updated_when_secondary_file_disallowed(self, tmp_path: Path) -> None:
        state = self._multi_file_state(tmp_path)
        with patch(
            "vibeops.services.review.validate",
            return_value=TerraformValidationResult(ok=True),
        ):
            new_state, _ = apply_user_edit(state, "outputs.tf", _SNEAKY_BUCKET)

        assert new_state.terraform_files["outputs.tf"] == ""

    def test_clean_outputs_edit_still_accepted(self, tmp_path: Path) -> None:
        """Sanity: a valid outputs.tf edit (no resources) still passes the dir-wide check."""
        state = self._multi_file_state(tmp_path)
        valid_output = 'output "vm_name" { value = "gpu_vm" }\n'
        with patch(
            "vibeops.services.review.validate",
            return_value=TerraformValidationResult(ok=True),
        ):
            new_state, err = apply_user_edit(state, "outputs.tf", valid_output)

        assert err is None
        assert new_state.terraform_files["outputs.tf"] == valid_output


class TestEditFilenameSanitization:
    """Reject path traversal / non-whitelisted filenames BEFORE anything touches disk."""

    @pytest.mark.parametrize(
        "bad_name",
        [
            "../secrets.tf",
            "..\\..\\evil.tf",
            "/etc/passwd",
            "sub/dir.tf",
            "provider.tf",  # a valid .tf name, but not one of the editable files
            "main.tf.bak",
            "evil.txt",
            "",
        ],
    )
    def test_illegal_filename_rejected(self, tmp_path: Path, bad_name: str) -> None:
        state = _state(tmp_path)
        new_state, err = apply_user_edit(state, bad_name, _SNEAKY_BUCKET)

        assert err is not None
        assert "Illegal filename" in err
        # No state mutation on rejection.
        assert new_state.terraform_files == state.terraform_files

    def test_traversal_filename_writes_nothing_to_disk(self, tmp_path: Path) -> None:
        state = _state(tmp_path)
        apply_user_edit(state, "../escape.tf", _SNEAKY_BUCKET)

        assert not (tmp_path.parent / "escape.tf").exists()
        assert not (tmp_path / "escape.tf").exists()
        # main.tf is left untouched.
        assert (tmp_path / "main.tf").read_text(encoding="utf-8") == _ORIGINAL

    def test_editable_filename_passes_the_gate(self, tmp_path: Path) -> None:
        """The known editable files clear the filename gate (allowlist then vets content)."""
        (tmp_path / "variables.tf").write_text("", encoding="utf-8")
        state = GraphState(
            user_prompt="test",
            stage=FlowStage.AWAITING_APPROVAL,
            terraform_dir=str(tmp_path),
            terraform_files={"main.tf": _ORIGINAL, "variables.tf": ""},
            terraform_files_original={"main.tf": _ORIGINAL, "variables.tf": ""},
        )
        valid_vars = 'variable "project_id" { type = string }\n'
        with patch(
            "vibeops.services.review.validate",
            return_value=TerraformValidationResult(ok=True),
        ):
            new_state, err = apply_user_edit(state, "variables.tf", valid_vars)

        assert err is None
        assert new_state.terraform_files["variables.tf"] == valid_vars
